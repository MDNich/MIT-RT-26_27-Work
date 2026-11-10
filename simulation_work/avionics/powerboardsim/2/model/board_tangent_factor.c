/* Factor an assembled symmetric positive-definite tangent on macOS.
   The caller owns the CSC arrays and retains them until close_factor. */
#include <Accelerate/Accelerate.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct {
    SparseOpaqueFactorization_Double factor;
    int equations;
} TangentFactor;

void *open_factor(int n, long *starts, int *rows, double *values,
                  unsigned long limit, unsigned long sizes[2]) {
    SparseMatrixStructure structure = {
        .rowCount = n, .columnCount = n, .columnStarts = starts,
        .rowIndices = rows, .blockSize = 1,
        .attributes = {.kind = SparseSymmetric, .triangle = SparseUpperTriangle}
    };
    SparseSymbolicFactorOptions options = {
        .orderMethod = SparseOrderMetis, .malloc = malloc, .free = free
    };
    SparseOpaqueSymbolicFactorization symbolic =
        SparseFactor(SparseFactorizationCholesky, structure, options);
    if (symbolic.status != SparseStatusOK) {
        fprintf(stderr, "Symbolic factorization status %d\n",symbolic.status);
        return NULL;
    }
    sizes[0] = symbolic.factorSize_Double;
    sizes[1] = symbolic.workspaceSize_Double;
    fprintf(stderr,"Factor and workspace bytes: %lu and %lu\n",sizes[0],sizes[1]);
    if (sizes[0] > limit || sizes[1] > limit - sizes[0]) {
        SparseCleanup(symbolic);
        return NULL;
    }
    SparseMatrix_Double matrix = {.structure = structure, .data = values};
    SparseOpaqueFactorization_Double factor = SparseFactor(symbolic,matrix);
    SparseCleanup(symbolic);
    if (factor.status != SparseStatusOK) {
        fprintf(stderr, "Numeric Cholesky status %d\n",factor.status);
        SparseCleanup(factor);
        return NULL;
    }
    TangentFactor *result = malloc(sizeof(*result));
    if (!result) { SparseCleanup(factor); return NULL; }
    result->factor = factor;
    result->equations = n;
    return result;
}

void solve_factor(TangentFactor *factor, int columns, double *data) {
    int n = factor->equations;
    DenseMatrix_Double rhs = {.rowCount = n, .columnCount = columns,
                              .columnStride = n, .data = data};
    SparseSolve(factor->factor,rhs);
}

void close_factor(TangentFactor *factor) {
    SparseCleanup(factor->factor);
    free(factor);
}
