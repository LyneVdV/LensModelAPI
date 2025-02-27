__author__ = 'aymgal'


import os
import numpy as np
# from astropy.coordinates import SkyCoord

from coolest.template.json import JSONSerializer
from coolest.api.coordinates import Coordinates


def convert_image_to_data_units(image, pixel_size, mag_tot, mag_zero_point):
    """
    Rescale an image so that it has units of electrons per second (e/s),
    which is the default data units in COOLEST.
    :param pixel_size: pixel size (in arcsec) of the image
    :param image: input image (whatever units)
    :param mag_tot: target total magnitude, integrated over the whole image
    :param mag_zero_point: magnitude zero point of the observation (magnitude that corresponds to 1 e/s)
    """
    pixel_area = pixel_size**2
    flux_tot = np.sum(image) * pixel_area
    image_unit_flux = image / flux_tot
    delta_mag = mag_tot - mag_zero_point
    flux_unit_mag = 10 ** ( - delta_mag / 2.5 )
    return image_unit_flux * flux_unit_mag


def get_coolest_object(file_path, verbose=False, **kwargs_serializer):
    if not os.path.isabs(file_path):
        file_path = os.path.abspath(file_path)
    serializer = JSONSerializer(file_path, **kwargs_serializer)
    return serializer.load(verbose=verbose)


def get_coordinates(coolest_object, offset_ra=0., offset_dec=0.):
    nx, ny = coolest_object.observation.pixels.shape
    pix_scl = coolest_object.instrument.pixel_size
    half_size_x, half_size_y = nx * pix_scl / 2., ny * pix_scl / 2.
    ra_at_xy_0  = - half_size_x + pix_scl / 2.  # position of x=0 with respect to bottom left pixel
    dec_at_xy_0 = - half_size_y + pix_scl / 2.  # position of y=0 with respect to bottom left pixel
    matrix_pix2ang = pix_scl * np.eye(2)  # transformation matrix pixel <-> angle
    
    coordinates = Coordinates(nx, ny, matrix_pixel_to_radec=matrix_pix2ang,
                              ra_at_xy_0=ra_at_xy_0 + offset_ra, 
                              dec_at_xy_0=dec_at_xy_0 + offset_dec)
    return coordinates


def get_coordinates_set(coolest_file_list, reference=0):
    coordinates_list = []
    for coolest_file in coolest_file_list:

        # TODO: compute correct offsets when each file has
        # obs = self.coolest.observation
        # sky_coord = SkyCoord(obs.ra, obs.dec, frame='icrs')
        # ra, dec = sky_coord.to_string(style='hmsdms').split(' ')

        coordinates = get_coordinates(coolest_file)
        coordinates_list.append(coordinates)
    return coordinates_list


def array2image(array, nx=0, ny=0):
    """Convert a 1d array into a 2d array.

    Note: this only works when length of array is a perfect square, or else if
    nx and ny are provided

    :param array: image values
    :type array: array of size n**2
    :returns:  2d array
    :raises: AttributeError, KeyError
    """
    if nx == 0 or ny == 0:
        # Avoid turning n into a JAX-traced object with jax.numpy.sqrt
        n = int(math.sqrt(len(array)))
        if n**2 != len(array):
            err_msg = f"Input array size {len(array)} is not a perfect square."
            raise ValueError(err_msg)
        nx, ny = n, n
    image = array.reshape(int(nx), int(ny))
    return image


def image2array(image):
    """Convert a 2d array into a 1d array.

    :param array: image values
    :type array: array of size (n,n)
    :returns:  1d array
    :raises: AttributeError, KeyError
    """
    # nx, ny = image.shape  # find the size of the array
    # imgh = np.reshape(image, nx * ny)  # change the shape to be 1d
    # return imgh
    return image.ravel()


def read_json_param(file_list, file_names, lens_light=False):
    """
    Read several json files already containing a model with the results of this model fitting

    INPUT
    -----
    file_list: list, list of path or names of the file to read
    file_names: list, list of shorter names to distinguish the files
    lens_light: bool, if True, computes the lens light kwargs as well (not yet implemented)

    OUTPUT
    ------
     param_all_lens, param_all_source: organized dictionnaries readable by plotting function
    """

    param_all_lens = {}
    param_all_source = {}
    for idx_file, file_name in enumerate(file_list):

        print(file_names[idx_file])
        decoder = JSONSerializer(file_name, indent=2)
        lens_coolest = decoder.load()

        if lens_coolest.mode == 'MAP':
            print('LENS COOLEST : ', lens_coolest.mode)
        else:
            print('LENS COOLEST IS NOT MAP, BUT IS ', lens_coolest.mode)

        lensing_entities_list = lens_coolest.lensing_entities

        param_lens = {}
        param_source = {}

        if lensing_entities_list is not None:

            creation_lens_source_light = True

            idx_lens = 0
            idx_lens_light = 0
            idx_source = 0
            idx_ps = 0

            min_red = 0
            max_red = 5
            creation_red_list = True
            red_list = []
            MultiPlane = False
            for lensing_entity in lensing_entities_list:
                red_list.append(lensing_entity.redshift)
            min_red = np.min(red_list)
            max_red = np.max(red_list)

            for lensing_entity in lensing_entities_list:
                if lensing_entity.type == "galaxy":
                    galac = lensing_entity

                    if galac.redshift > min_red:
                        # SOURCE OF LIGHT
                        light_list = galac.light_model
                        for light in light_list:

                            if light.type == 'Sersic':
                                read_sersic(light, param_source)
                                idx_source += 1
                            else:
                                print('Light Type ', light.type, ' not yet implemented.')

                    if galac.redshift < max_red:
                        # LENSING GALAXY
                        if galac.redshift > min_red:
                            MultiPlane = True
                            print('Multiplane lensing to consider.')
                        mass_list = galac.mass_model
                        for mass in mass_list:

                            if mass.type == 'PEMD':
                                read_pemd(mass, param_lens)
                                idx_lens += 1
                            elif mass.type == 'SIE':
                                read_sie(mass, param_lens)
                                idx_lens += 1
                            else:
                                print('Mass Type ', mass.type, ' not yet implemented.')

                    if (galac.redshift <= min_red) and (galac.redshift >= max_red):
                        print('REDSHIFT ', galac.redshift, ' is not in the range ]', min_red, ',', max_red, '[')

                elif lensing_entity.type == "external_shear":
                    shear_list = lensing_entity.mass_model
                    for shear_idx in shear_list:

                        if shear_idx.type == 'ExternalShear':
                            read_shear(shear_idx, param_lens)
                            idx_lens += 1
                        else:
                            print("type of Shear ", shear_idx.type, " not implemented")
                else:
                    print("Lensing entity of type ", lensing_enity.type, " is unknown.")

        param_all_lens[file_names[idx_file]] = param_lens
        param_all_source[file_names[idx_file]] = param_source

    return param_all_lens, param_all_source


def read_shear(mass, param={}, prefix='SHEAR_0_'):
    """
    Reads the parameters of a coolest.template.classes.profiles.mass.ExternalShear object

    INPUT
    -----
    mass : coolest.template.classes.profiles.mass.ExternalShear object
    param : dict, already existing dictionnary with ordered parameters readable by plotting function
    prefix : str, prefix to use in saving parameters names

    OUTPUT
    ------
    param : updated param
    """

    for mass_name, mass_param in mass.parameters.items():
        p = getattr(mass_param.point_estimate, 'value')
        p_84 = getattr(mass_param.posterior_stats, 'percentile_84th')
        p_16 = getattr(mass_param.posterior_stats, 'percentile_16th')
        p_med = getattr(mass_param.posterior_stats, 'median')
        p_mean = getattr(mass_param.posterior_stats, 'mean')
        latex_name = getattr(mass_param, 'latex_str')
        if mass_name == 'gamma_ext':
            param[prefix + 'gamma_ext'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                           'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif mass_name == 'phi_ext':
            param[prefix + 'phi_ext'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                         'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        else:
            print(shear_name, " not known")
    print('\t Shear correctly added')

    return param


def read_pemd(mass, param={}, prefix='PEMD_0_'):
    """
    Reads the parameters of a coolest.template.classes.profiles.mass.PEMD object

    INPUT
    -----
    mass : coolest.template.classes.profiles.mass.PEMD object
    param : dict, already existing dictionnary with ordered parameters readable by plotting function
    prefix : str, prefix to use in saving parameters names

    OUTPUT
    ------
    param : updated param
    """

    for mass_name, mass_param in mass.parameters.items():
        p = getattr(mass_param.point_estimate, 'value')
        p_84 = getattr(mass_param.posterior_stats, 'percentile_84th')
        p_16 = getattr(mass_param.posterior_stats, 'percentile_16th')
        p_med = getattr(mass_param.posterior_stats, 'median')
        p_mean = getattr(mass_param.posterior_stats, 'mean')
        latex_name = getattr(mass_param, 'latex_str')
        if mass_name == 'theta_E':
            param[prefix + 'theta_E'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                         'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif mass_name == 'q':
            param[prefix + 'q'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                   'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif mass_name == 'phi':
            param[prefix + 'phi'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                     'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif mass_name == 'center_x':
            param[prefix + 'cx'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                    'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif mass_name == 'center_y':
            param[prefix + 'cy'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                    'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif mass_name == 'gamma':
            param[prefix + 'gamma'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                       'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        else:
            print(mass_name, " not known")

    print('\t PEMD correctly added')

    return param


def read_sie(mass, param={}, prefix='SIE_0_'):
    """
    Reads the parameters of a coolest.template.classes.profiles.mass.SIE object

    INPUT
    -----
    mass : coolest.template.classes.profiles.mass.SIE object
    param : dict, already existing dictionnary with ordered parameters readable by plotting function
    prefix : str, prefix to use in saving parameters names

    OUTPUT
    ------
    param : updated param
    """

    for mass_name, mass_param in mass.parameters.items():
        p = getattr(mass_param.point_estimate, 'value')
        p_84 = getattr(mass_param.posterior_stats, 'percentile_84th')
        p_16 = getattr(mass_param.posterior_stats, 'percentile_16th')
        p_med = getattr(mass_param.posterior_stats, 'median')
        p_mean = getattr(mass_param.posterior_stats, 'mean')
        latex_name = getattr(mass_param, 'latex_str')
        if mass_name == 'theta_E':
            param[prefix + 'theta_E'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                         'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif mass_name == 'q':
            param[prefix + 'q'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                   'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif mass_name == 'phi':
            param[prefix + 'phi'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                     'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif mass_name == 'center_x':
            param[prefix + 'cx'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                    'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif mass_name == 'center_y':
            param[prefix + 'cy'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                    'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        else:
            print(mass_name, " not known")

    print('\t SIE correctly added')

    return param


def read_sersic(light, param={}, prefix='Sersic_0_'):
    """
    Reads the parameters of a coolest.template.classes.profiles.light.Sersic object

    INPUT
    -----
    mass : coolest.template.classes.profiles.light.Sersic object
    param : dict, already existing dictionnary with ordered parameters readable by plotting function
    prefix : str, prefix to use in saving parameters names

    OUTPUT
    ------
    param : updated param
    """

    for light_name, light_param in light.parameters.items():
        p = getattr(light_param.point_estimate, 'value')
        p_84 = getattr(light_param.posterior_stats, 'percentile_84th')
        p_16 = getattr(light_param.posterior_stats, 'percentile_16th')
        p_med = getattr(light_param.posterior_stats, 'median')
        p_mean = getattr(light_param.posterior_stats, 'mean')
        latex_name = getattr(light_param, 'latex_str')
        if light_name == 'I_eff':
            param[prefix + 'A'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                   'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif light_name == 'n':
            param[prefix + 'n_sersic'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                          'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif light_name == 'theta_eff':
            param[prefix + 'R_sersic'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                          'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif light_name == 'q':
            param[prefix + 'q'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                   'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif light_name == 'phi':
            param[prefix + 'phi'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                     'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif light_name == 'center_x':
            param[prefix + 'cx'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                    'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        elif light_name == 'center_y':
            param[prefix + 'cy'] = {'point_estimate': p, 'percentile_84th': p_84, 'percentile_16th': p_16,
                                    'median': p_med, 'mean': p_mean, 'latex_str': latex_name}
        else:
            print(light_name, " not known")

    print('\t Sersic correctly added')

    return param
