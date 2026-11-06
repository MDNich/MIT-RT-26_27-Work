"""Independent retained Al backing with explicitly regularized latent heat."""
import numpy as np

from aluminium_phase_enthalpy import caloric, equilibrium
from moving_surface_transient import Wall


class AluminiumBackingWall(Wall):
    def __init__(self, cfg, liner_cells, case_cells):
        if cfg['case_material'] != 'al':
            raise ValueError('This backing requires the aluminium configuration')
        super().__init__(cfg, liner_cells, case_cells)
        self.width_K = cfg['al_fusion_width_K']

    def casing(self, temperature_C):
        return caloric(temperature_C, self.width_K)

    def phase(self, temperature_C):
        """Recover equilibrium phase fractions from the energy in the smeared law."""
        h, _ = self.casing(temperature_C)
        _, liquid = equilibrium(h)
        return dict(max_cell_liquid=float(np.max(liquid)), min_cell_liquid=float(np.min(liquid)),
                    mass_fraction_liquid=float(self.case_mass @ liquid / self.case_mass.sum()))
