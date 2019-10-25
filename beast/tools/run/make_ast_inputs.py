#!/usr/bin/env python
"""
Script to run the BEAST on the PHAT-like data.
Assumes that the datamodel.py file exists in the same directory as this script.
  And it must be called datamodel.py
"""

# system imports
import argparse
import os
import numpy as np
from astropy.table import Table

# BEAST imports
from beast.observationmodel.ast.make_ast_input_list import (
    pick_models,
    pick_models_toothpick_style,
)
from beast.observationmodel.ast import make_ast_xy_list
from beast.tools import verify_params

import datamodel
import importlib

importlib.reload(make_ast_xy_list)


def make_ast_inputs(flux_bin_method=True):
    """
    Make the list of artificial stars to be run through the photometry pipeline

    Parameters
    ----------
    flux_bin_method : boolean (default=True)
        If True, use the flux bin method to select SEDs.  If False, randomly
        select SEDs from the model grid.

    """

    # before doing ANYTHING, force datamodel to re-import (otherwise, any
    # changes within this python session will not be loaded!)
    importlib.reload(datamodel)
    # check input parameters
    verify_params.verify_input_format(datamodel)

    # construct magnitude cuts

    mag_cuts = datamodel.ast_maglimit
    obsdata = datamodel.get_obscat(datamodel.obsfile, datamodel.filters)

    if len(mag_cuts) == 1:
        tmp_cuts = mag_cuts
        min_mags = np.zeros(len(datamodel.filters))
        for k, filtername in enumerate(obsdata.filters):
            sfiltername = obsdata.data.resolve_alias(filtername)
            sfiltername = sfiltername.replace("rate", "vega")
            sfiltername = sfiltername.replace("RATE", "VEGA")
            keep, = np.where(obsdata[sfiltername] < 99.0)
            min_mags[k] = np.percentile(obsdata[keep][sfiltername], 90.0)

        # max. mags from the gst observation cat.
        mag_cuts = min_mags + tmp_cuts

    # --------------------
    # select SEDs
    # --------------------

    Nrealize = datamodel.ast_realization_per_model
    Nfilters = datamodel.ast_bands_above_maglimit

    # file names for stars and corresponding SED parameters
    outfile_seds = "./{0}/{0}_inputAST_seds.txt".format(datamodel.project)
    outfile_params = "./{0}/{0}_ASTparams.fits".format(datamodel.project)

    # if the SED file doesn't exist, create SEDs
    if not os.path.isfile(outfile_seds):

        print('Selecting SEDs for ASTs')

        if flux_bin_method:

            N_fluxes = datamodel.ast_n_flux_bins
            min_N_per_flux = datamodel.ast_n_per_flux_bin
            bins_outfile = "./{0}/{0}_ASTfluxbins.txt".format(datamodel.project)
            modelsedgrid_filename = './{0}/{0}_seds.grid.hd5'.format(datamodel.project)

            chosen_seds = pick_models_toothpick_style(
                modelsedgrid_filename,
                datamodel.filters,
                mag_cuts,
                Nfilters,
                N_fluxes,
                min_N_per_flux,
                outfile=outfile_seds,
                outfile_params=outfile_params,
                bins_outfile=bins_outfile,
            )

        else:

            N_models = datamodel.ast_models_selected_per_age

            chosen_seds = pick_models(
                modelsedgrid_filename,
                datamodel.filters,
                mag_cuts,
                Nfilter=Nfilters,
                N_stars=N_models,
                Nrealize=Nrealize,
                outfile=outfile_seds,
                outfile_params=outfile_params,
            )

    # if the SED file does exist, read them in
    else:
        print('Reading existing AST SEDs')
        chosen_seds = Table.read(outfile_seds, format='ascii')

    # --------------------
    # assign positions
    # --------------------

    # if we want ASTs with positions included (rather than just the fluxes from
    # the section above)
    if datamodel.ast_with_positions:

        print('Assigning positions to artifical stars')

        outfile = "./{0}/{0}_inputAST.txt".format(datamodel.project)


        # if we're replicating SEDs across source density bins
        if datamodel.ast_source_density_table is not None:
            make_ast_xy_list.pick_positions_from_map(
                obsdata,
                chosen_seds,
                datamodel.ast_source_density_table,
                datamodel.ast_N_bins,
                datamodel.ast_realization_per_model,
                outfile=outfile,
                refimage=datamodel.ast_reference_image,
                refimage_hdu=1,
                wcs_origin=1,
                Nrealize=1,
                set_coord_boundary=datamodel.ast_coord_boundary,
                region_from_filters='all',
            )

        # if we're replicating SEDs across background bins
        elif datamodel.ast_background_table is not None:
            make_ast_xy_list.pick_positions_from_map(
                obsdata,
                chosen_seds,
                datamodel.ast_background_table,
                datamodel.ast_N_bins,
                datamodel.ast_realization_per_model,
                outfile=outfile,
                refimage=datamodel.ast_reference_image,
                refimage_hdu=1,
                wcs_origin=1,
                Nrealize=1,
                set_coord_boundary=datamodel.ast_coord_boundary,
            )

        # if we're not using SD/background maps, SEDs will be distributed
        # based on catalog sources
        else:
            make_ast_xy_list.pick_positions(
                obsdata,
                outfile,
                datamodel.ast_pixel_distribution,
                refimage=datamodel.ast_reference_image,
            )


if __name__ == "__main__":
    # commandline parser
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--flux_bin_method",
        default=1,
        type=int,
        help="Choose SEDs using flux bin method (1, default) or not (0)",
    )

    args = parser.parse_args()

    make_ast_inputs(flux_bin_method=bool(args.flux_bin_method))

    # print help if no arguments
    if not any(vars(args).values()):
        parser.print_help()
