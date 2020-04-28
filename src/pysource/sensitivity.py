import numpy as np
from sympy import cos, sin

from devito import (TimeFunction, Function, Inc, Dimension, grad,
                    DefaultDimension, Eq, ConditionalDimension)
from devito.tools import as_tuple

from wave_utils import sub_time


def func_name(freq=None, isic=False):
    """
    Get key for imaging condition/linearized source function
    """
    if freq is None:
        return 'isic' if isic else 'corr'
    else:
        return 'isic_freq' if isic else 'corr_freq'


def grad_expr(gradm, u, v, model, w=1, freq=None, dft_sub=None, isic=False):
    """
    Gradient update stencil

    Parameters
    ----------
    u: TimeFunction or Tuple
        Forward wavefield (tuple of fields for TTI or dft)
    v: TimeFunction or Tuple
        Adjoint wavefield (tuple of fields for TTI)
    model: Model
        Model structure
    w: Float or Expr (optional)
        Weight for the gradient expression (default=1)
    freq: Array
        Array of frequencies for on-the-fly DFT
    factor: int
        Subsampling factor for DFT
    isic: Bool
        Whether or not to use inverse scattering imaging condition (not supported yet)
    """
    ic_func = ic_dict[func_name(freq=freq, isic=isic)]
    expr = ic_func(as_tuple(u)[0], as_tuple(v)[0], model, freq=freq, factor=dft_sub)
    return [Eq(gradm, expr + gradm)]


def corr_freq(u, v, model, freq=None, dft_sub=None, **kwargs):
    """
    Standard cross-correlation imaging condition with on-th-fly-dft

    Parameters
    ----------
    u: TimeFunction or Tuple
        Forward wavefield (tuple of fields for TTI or dft)
    v: TimeFunction or Tuple
        Adjoint wavefield (tuple of fields for TTI)
    model: Model
        Model structure
    freq: Array
        Array of frequencies for on-the-fly DFT
    factor: int
        Subsampling factor for DFT
    """
    # Subsampled dft time axis
    time = model.grid.time_dim
    dt = time.spacing
    tsave, factor = sub_time(time, dft_sub)
    ufr, ufi = u
    # Frequencies
    nfreq = freq.shape[0]
    f = Function(name='f', dimensions=(ufr.dimensions[0],), shape=(nfreq,))
    f.data[:] = freq[:]
    omega_t = 2*np.pi*f*tsave*factor*dt
    # Gradient weighting is (2*np.pi*f)**2/nt
    w = (2*np.pi*f)**2/time.symbolic_max
    expr = w*(ufr*cos(omega_t) - ufi*sin(omega_t))*v
    return expr


def corr_fields(u, v, model, **kwargs):
    """
    Cross correlation of forward and adjoint wavefield

    Parameters
    ----------
    u: TimeFunction or Tuple
        Forward wavefield (tuple of fields for TTI or dft)
    v: TimeFunction or Tuple
        Adjoint wavefield (tuple of fields for TTI)
    model: Model
        Model structure
    """
    w = kwargs.get('w', model.time_dim.spacing / model.rho)
    return  - w * v * u.dt2


def isic_g(u, v, model, **kwargs):
    """
    Inverse scattering imaging condition

    Parameters
    ----------
    u: TimeFunction or Tuple
        Forward wavefield (tuple of fields for TTI or dft)
    v: TimeFunction or Tuple
        Adjoint wavefield (tuple of fields for TTI)
    model: Model
        Model structure
    """
    w = model.time_dim.spacing / model.rho
    return w * (u * v.dt2 * model.m + grad(u).T * grad(v))


def isic_freq_g(u, v, model, **kwargs):
    """
    Inverse scattering imaging condition

    Parameters
    ----------
    u: TimeFunction or Tuple
        Forward wavefield (tuple of fields for TTI or dft)
    v: TimeFunction or Tuple
        Adjoint wavefield (tuple of fields for TTI)
    model: Model
        Model structure
    """
    freq = kwargs.get('freq')
    # Subsampled dft time axis
    time = model.grid.time_dim
    dt = time.spacing
    tsave, factor = sub_time(time, kwargs.get('factor'))
    ufr, ufi = u
    # Frequencies
    nfreq =freq.shape[0]
    f = Function(name='f', dimensions=(ufr.dimensions[0],), shape=(nfreq,))
    f.data[:] = freq[:]
    omega_t = 2*np.pi*f*tsave*factor*dt
    # Gradient weighting is (2*np.pi*f)**2/nt
    w = (2*np.pi*f)**2/time.symbolic_max
    expr =  (w*(ufr*cos(omega_t) - ufi*sin(omega_t))*v* model.m -
             factor/time.symbolic_max * (grad(ufr*cos(omega_t) - ufi*sin(omega_t)).T * grad(v)))
    return expr


def lin_src(model, u, isic=False):
    """
    Source for linearized modeling

    Parameters
    ----------
    u: TimeFunction or Tuple
        Forward wavefield (tuple of fields for TTI or dft)
    model: Model
        Model containing the perturbation dm
    """
    ls_func = ls_dict[func_name(isic=isic)]
    return ls_func(model, u)


def basic_src(model, u, **kwargs):
    """
    Basic source for linearized modeling

    Parameters
    ----------
    u: TimeFunction or Tuple
        Forward wavefield (tuple of fields for TTI or dft)
    model: Model
        Model containing the perturbation dm
    """
    w = - model.dm * model.irho
    if type(u) is tuple:
        return (w * u[0].dt2, w * u[1].dt2)
    return w * u.dt2


def isic_s(model, u, **kwargs):
    """
    ISIC source for linearized modeling

    Parameters
    ----------
    u: TimeFunction or Tuple
        Forward wavefield (tuple of fields for TTI or dft)
    model: Model
        Model containing the perturbation dm
    """
    m, dm, irho = model.m, model.dm, model.irho
    so = irho.space_order//2
    du_aux = sum([getattr(getattr(u, 'd%s' % d.name)(fd_order=so) * dm * irho,
                           'd%s' % d.name)(fd_order=so)
                  for d in u.space_dimensions])
    return dm * irho * u.dt2 * m - du_aux


ic_dict = {'isic_freq': isic_freq_g, 'corr_freq': corr_freq, 'isic': isic_g, 'corr': corr_fields}
ls_dict = {'isic': isic_s, 'corr': basic_src}