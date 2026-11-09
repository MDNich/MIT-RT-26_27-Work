"""Resolve each film subject to its matching native model and recorded solver attempt."""
def branch_for(variant,subject):
    if variant.startswith('flush_') and subject not in ('original','refined'):
        return variant+'_surf1'
    return variant

def native_case(variant,subject):
    branch=branch_for(variant,subject)
    if subject.startswith('psd_') and variant!='bare':
        return branch+'_'+subject+'_private1'
    return branch+'_'+subject
