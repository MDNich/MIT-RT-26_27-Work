"""Stateful Arrhenius pyrolysis model for Ansys MAPDL UserMatTh.

Target solver: Ansys Mechanical / MAPDL 2026 R1 (26.1), pure transient
thermal elements such as SOLID278 or SOLID279.

The routine expects eleven TB,USER properties at every TBTEMP point, in SI:

    prop[0] = k_virgin     [W m^-1 K^-1]
    prop[1] = k_char       [W m^-1 K^-1]
    prop[2] = cp_virgin    [J kg^-1 K^-1]
    prop[3] = cp_char      [J kg^-1 K^-1]
    prop[4] = rho_virgin   [kg m^-3]
    prop[5] = rho_char     [kg m^-3]
    prop[6] = A            [s^-1]
    prop[7] = Ea           [J mol^-1]
    prop[8] = order_n      [-]
    prop[9] = delta_h_pyr  [J kg^-1], positive for endothermic pyrolysis
    prop[10] = temp_offset [K], add to the solver temperature before Arrhenius

For a Mechanical model using degrees Celsius, set temp_offset = 273.15. For
a model whose solver temperature is already Kelvin, set temp_offset = 0.0.

State variables:

    SVAR1 = alpha          [-], 0 virgin and 1 fully charred
    SVAR2 = alpha_dot      [s^-1], optional diagnostic

The Arrhenius equation is integrated analytically over each increment:

    dalpha/dt = A exp(-Ea / (R T)) (1 - alpha)^n

Thermal properties are linearly mixed between virgin and char states.
Pyrolysis enthalpy is applied as a negative heat generation per unit mass,
which is the convention for UserMatTh with pure thermal elements. Do not use
this implementation unchanged with coupled SOLID225/226/227 elements, where
Ansys interprets hgen per unit volume and restricts state/density updates.

This model describes solid decomposition and char formation. It does not
remove elements, move the hot boundary, transport pyrolysis gas, or calculate
surface recession.
"""

import math
import sys

import grpc
from mapdl import *  # noqa: F403 - supplied by the Ansys Python UPF runtime


GAS_CONSTANT = 8.31446261815324  # J mol^-1 K^-1
MIN_TEMPERATURE = 1.0  # K, protects the exponential from invalid input
MAX_EXPONENT = 700.0
MAX_DELTA_ALPHA = 0.05
MIN_CUT_FACTOR = 0.10

_first_call = True
_missing = object()


def _get(obj, *names, default=_missing):
    """Return the first protobuf field found among names."""
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    if default is not _missing:
        return default
    raise AttributeError("Missing protobuf field: " + " or ".join(names))


def _set_scalar(obj, value, *names):
    """Set a scalar protobuf field, allowing minor API naming differences."""
    for name in names:
        if hasattr(obj, name):
            setattr(obj, name, value)
            return
    raise AttributeError("Missing response field: " + " or ".join(names))


def _set_repeated(obj, values, *names):
    """Set a repeated protobuf field."""
    for name in names:
        if hasattr(obj, name):
            getattr(obj, name)[:] = list(values)
            return
    raise AttributeError("Missing response field: " + " or ".join(names))


def _clamp(value, lower, upper):
    return max(lower, min(upper, value))


def _integrate_conversion(alpha_old, rate_constant, order_n, dt):
    """Analytically integrate d(alpha)/dt=k*(1-alpha)^n."""
    alpha_old = _clamp(alpha_old, 0.0, 1.0)
    if dt <= 0.0 or rate_constant <= 0.0 or alpha_old >= 1.0:
        return alpha_old

    beta_old = max(1.0 - alpha_old, 0.0)
    if abs(order_n - 1.0) <= 1.0e-10:
        beta_new = beta_old * math.exp(-rate_constant * dt)
    else:
        power = 1.0 - order_n
        bracket = beta_old**power - power * rate_constant * dt
        if bracket <= 0.0:
            beta_new = 0.0
        else:
            beta_new = bracket ** (1.0 / power)

    return _clamp(1.0 - beta_new, alpha_old, 1.0)


def _validate_properties(prop):
    if len(prop) < 11:
        raise ValueError(
            "UserMatTh pyrolysis requires 11 TB,USER properties; "
            f"received {len(prop)}"
        )

    names = (
        "k_virgin",
        "k_char",
        "cp_virgin",
        "cp_char",
        "rho_virgin",
        "rho_char",
        "A",
        "Ea",
        "order_n",
        "delta_h_pyr",
        "temp_offset",
    )
    values = [float(value) for value in prop[:11]]

    for name, value in zip(names, values):
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite, got {value}")

    (
        k_v,
        k_c,
        cp_v,
        cp_c,
        rho_v,
        rho_c,
        a_pre,
        ea,
        order_n,
        delta_h,
        temp_offset,
    ) = values
    if min(k_v, k_c, cp_v, cp_c, rho_v, rho_c) <= 0.0:
        raise ValueError("Conductivity, specific heat, and density must be positive")
    if a_pre < 0.0 or ea < 0.0 or order_n <= 0.0 or delta_h < 0.0:
        raise ValueError("A and Ea must be nonnegative; n positive; delta_h nonnegative")

    return values


class MapdlUserService(MapdlUser_pb2_grpc.MapdlUserServiceServicer):  # noqa: F405
    """Python gRPC implementation of the MAPDL UserMatTh callback."""

    def UserMatTh(self, request, context):
        global _first_call

        try:
            if _first_call:
                print(">> Using Python UserMatTh Arrhenius pyrolysis model")
                _first_call = False

            response = MapdlUser_pb2.UserMatThResponse()  # noqa: F405

            prop = list(_get(request, "prop"))
            (
                k_v,
                k_c,
                cp_v,
                cp_c,
                rho_v,
                rho_c,
                a_pre,
                ea,
                order_n,
                delta_h,
                temp_offset,
            ) = _validate_properties(prop)

            ncomp = int(_get(request, "ncomp"))
            if ncomp <= 0:
                raise ValueError(f"ncomp must be positive, got {ncomp}")

            temp = float(_get(request, "Temp", "temp"))
            dtemp = float(_get(request, "dTemp", "dtemp", default=0.0))
            dt = max(float(_get(request, "dTime", "dtime", default=0.0)), 0.0)
            temperature_mid = max(
                temp + 0.5 * dtemp + temp_offset,
                MIN_TEMPERATURE,
            )

            nstatev = int(_get(request, "nStatev", "nstatev", default=0))
            state = list(_get(request, "ustatev", default=[]))
            if len(state) < nstatev:
                state.extend([0.0] * (nstatev - len(state)))
            alpha_old = _clamp(float(state[0]) if state else 0.0, 0.0, 1.0)

            exponent = _clamp(
                -ea / (GAS_CONSTANT * temperature_mid),
                -MAX_EXPONENT,
                MAX_EXPONENT,
            )
            rate_constant = a_pre * math.exp(exponent)
            alpha_new = _integrate_conversion(alpha_old, rate_constant, order_n, dt)
            delta_alpha = alpha_new - alpha_old
            alpha_dot = delta_alpha / dt if dt > 0.0 else 0.0

            conductivity = (1.0 - alpha_new) * k_v + alpha_new * k_c
            specific_heat = (1.0 - alpha_new) * cp_v + alpha_new * cp_c
            density = (1.0 - alpha_new) * rho_v + alpha_new * rho_c

            tgrad = list(_get(request, "tgrad", default=[]))
            if len(tgrad) < ncomp:
                tgrad.extend([0.0] * (ncomp - len(tgrad)))
            flux = [-conductivity * float(tgrad[i]) for i in range(ncomp)]
            dudg = [0.0] * ncomp
            dfdt = [0.0] * ncomp
            dfdg = [0.0] * (ncomp * ncomp)
            for i in range(ncomp):
                dfdg[i * ncomp + i] = -conductivity

            if not state:
                state = [alpha_new]
            else:
                state[0] = alpha_new
            if len(state) >= 2:
                state[1] = alpha_dot

            base_hgen = float(_get(request, "hgen", default=0.0))
            hgen = base_hgen - delta_h * alpha_dot

            request_cut = delta_alpha > MAX_DELTA_ALPHA
            if request_cut:
                cut_factor = _clamp(
                    MAX_DELTA_ALPHA / max(delta_alpha, 1.0e-30),
                    MIN_CUT_FACTOR,
                    0.95,
                )
            else:
                cut_factor = 1.0

            _set_scalar(response, 1 if request_cut else 0, "keycut")
            _set_scalar(response, cut_factor, "cutFactor", "cutfactor")
            _set_repeated(response, state, "ustatev")
            _set_scalar(response, specific_heat, "dudt")
            _set_repeated(response, dudg, "dudg")
            _set_repeated(response, flux, "flux")
            _set_repeated(response, dfdt, "dfdt")
            _set_repeated(response, dfdg, "dfdg")
            _set_scalar(response, hgen, "hgen")
            _set_scalar(response, density, "dens")

            # Reserved API arguments: preserve their incoming values when present.
            for name in ("var1", "var2", "var3", "var4", "var5", "var6"):
                if hasattr(response, name):
                    setattr(response, name, float(_get(request, name, default=0.0)))

            return response

        except Exception as exc:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "UserMatTh pyrolysis error: " + str(exc),
            )


if __name__ == "__main__":
    upf.launch(sys.argv[0])  # noqa: F405
