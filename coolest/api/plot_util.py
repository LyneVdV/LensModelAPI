__author__ = 'aymgal', 'Giorgos Vernardos'


import numpy as np
import warnings
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import ticker
from mpl_toolkits.axes_grid1 import make_axes_locatable
from scipy.spatial import Voronoi, voronoi_plot_2d
from matplotlib.colors import Normalize, LogNorm, TwoSlopeNorm


def plot_voronoi(ax, x, y, z, neg_values_as_bad=False, 
                 norm=None, cmap=None, zmin=None, zmax=None, 
                 edgecolor=None, zorder=1):

    if cmap is None:
        cmap = plt.get_cmap('inferno')
    if norm is None:
        if zmin is None:
            zmin = np.min(z)
        if zmax is None:
            zmax = np.max(z)
        norm = Normalize(zmin, zmax)

    # get voronoi regions
    voronoi_points = np.column_stack((x,y))
    vor = Voronoi(voronoi_points)
    new_regions, vertices = voronoi_finite_polygons_2d(vor)
    
    # get cell colors
    m = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap)

    # plot voronoi points
    #point_colors = [ m.to_rgba(v) for v in z ]
    #ax.scatter(voronoi_points[:,0],voronoi_points[:,1],c=point_colors)

    # plot voronoi cells
    for i, region in enumerate(new_regions):
        polygon = vertices[region]
        z_i = z[i]
        if neg_values_as_bad is True and z_i < 0.:
            cell_color = m.to_rgba(np.nan)
        else:
            cell_color = m.to_rgba(z_i)
        ax.fill(*zip(*polygon), facecolor=cell_color, edgecolor=edgecolor, zorder=zorder)
    return m


def voronoi_finite_polygons_2d(vor,radius=None):
    """
    Reconstruct infinite voronoi regions in a 2D diagram to finite
    regions.
    This function is taken from: https://gist.github.com/pv/8036995

    Parameters
    ----------
    vor : Voronoi
        Input diagram
    radius : float, optional
        Distance to 'points at infinity'.

    Returns
    -------
    regions : list of tuples
        Indices of vertices in each revised Voronoi regions.
    vertices : list of tuples
        Coordinates for revised Voronoi vertices. Same as coordinates
        of input vertices, with 'points at infinity' appended to the
        end.
    """

    if vor.points.shape[1] != 2:
        raise ValueError("Requires 2D input")

    new_regions = []
    new_vertices = vor.vertices.tolist()

    center = vor.points.mean(axis=0)
    if radius is None:
        radius = vor.points.ptp().max()

    # Construct a map containing all ridges for a given point
    all_ridges = {}
    for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
        all_ridges.setdefault(p1, []).append((p2, v1, v2))
        all_ridges.setdefault(p2, []).append((p1, v1, v2))

    # Reconstruct infinite regions
    for p1, region in enumerate(vor.point_region):
        vertices = vor.regions[region]

        if all(v >= 0 for v in vertices):
            # finite region
            new_regions.append(vertices)
            continue

        # reconstruct a non-finite region
        ridges = all_ridges[p1]
        new_region = [v for v in vertices if v >= 0]

        for p2, v1, v2 in ridges:
            if v2 < 0:
                v1, v2 = v2, v1
            if v1 >= 0:
                # finite ridge: already in the region
                continue

            # Compute the missing endpoint of an infinite ridge

            t = vor.points[p2] - vor.points[p1] # tangent
            t /= np.linalg.norm(t)
            n = np.array([-t[1], t[0]])  # normal

            midpoint = vor.points[[p1, p2]].mean(axis=0)
            direction = np.sign(np.dot(midpoint - center, n)) * n
            far_point = vor.vertices[v2] + direction * radius

            new_region.append(len(new_vertices))
            new_vertices.append(far_point.tolist())

        # sort region counterclockwise
        vs = np.asarray([new_vertices[v] for v in new_region])
        c = vs.mean(axis=0)
        angles = np.arctan2(vs[:,1] - c[1], vs[:,0] - c[0])
        new_region = np.array(new_region)[np.argsort(angles)]

        # finish
        new_regions.append(new_region.tolist())
        
    return new_regions, np.asarray(new_vertices)


def std_colorbar(mappable, label=None, fontsize=12, label_kwargs={}, **colorbar_kwargs):
    cb = plt.colorbar(mappable, **colorbar_kwargs)
    if label is not None:
        colorbar_kwargs.pop('label', None)
        cb.set_label(label, fontsize=fontsize, **label_kwargs)
    return cb

def std_colorbar_residuals(mappable, res_map, vmin, vmax, label=None, fontsize=12, 
                           label_kwargs={}, **colorbar_kwargs):
    if res_map.min() < vmin and res_map.max() > vmax:
        cb_extend = 'both'
    elif res_map.min() < vmin:
        cb_extend = 'min'
    elif res_map.max() > vmax:
        cb_extend = 'max'
    else:
        cb_extend = 'neither'
    colorbar_kwargs.update({'extend': cb_extend})
    return std_colorbar(mappable, label=label, fontsize=fontsize, 
                        label_kwargs=label_kwargs, **colorbar_kwargs)

def nice_colorbar(mappable, ax=None, position='right', pad=0.1, size='5%', label=None, fontsize=12, 
                  invisible=False, max_nbins=None,
                  divider_kwargs={}, colorbar_kwargs={}, label_kwargs={}):
    divider_kwargs.update({'position': position, 'pad': pad, 'size': size})
    if ax is None:
        ax = mappable.axes
    divider = make_axes_locatable(ax)
    cax = divider.append_axes(**divider_kwargs)
    if invisible:
        cax.axis('off')
        return None
    cb = plt.colorbar(mappable, cax=cax, **colorbar_kwargs)
    if label is not None:
        colorbar_kwargs.pop('label', None)
        cb.set_label(label, fontsize=fontsize, **label_kwargs)
    if position == 'top':
        cax.xaxis.set_ticks_position('top')
    if max_nbins is not None:
        cb.locator = ticker.MaxNLocator(nbins=max_nbins)
        cb.update_ticks()
    return cb

def nice_colorbar_residuals(mappable, res_map, vmin, vmax, ax=None, position='right', pad=0.1, size='5%', 
                            invisible=False, label=None, fontsize=12,
                            divider_kwargs={}, colorbar_kwargs={}, label_kwargs={}):
    if res_map.min() < vmin and res_map.max() > vmax:
        cb_extend = 'both'
    elif res_map.min() < vmin:
        cb_extend = 'min'
    elif res_map.max() > vmax:
        cb_extend = 'max'
    else:
        cb_extend = 'neither'
    colorbar_kwargs.update({'extend': cb_extend})
    return nice_colorbar(mappable, ax=ax, position=position, pad=pad, size=size, label=label, fontsize=fontsize,
                  invisible=invisible, colorbar_kwargs=colorbar_kwargs, label_kwargs=label_kwargs,
                  divider_kwargs=divider_kwargs)
