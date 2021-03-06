# -*- coding: utf-8 -*-

# Global imports
from PIL import Image
from simplejson import JSONDecodeError
import logging

# Django imports
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.template.response import TemplateResponse
from django.http import HttpResponse, HttpResponseRedirect
from django.utils import translation
from django.utils.translation import ugettext as _
from django.contrib.gis.geos import Point, LineString
from django.conf import settings

# Local imports
from map.models import *
from styles.models import Legend
from map.printing import name_image, map_image, legend_image, scalebar_image, imprint_image, get_image_size
from map.altitude import AltitudeProfile, height
from routing.core import MultiRoute, line_string_to_points, create_gpx, RouteParams
from routing.models import WeightCollection

logger = logging.getLogger(__name__)


def index(request):
    """
    Main map page.
    """
    weight_collections = WeightCollection.objects.all()
    default_tile_layer = TileLayer.objects.get(slug='mtb-map')
    tile_layers = TileLayer.objects.all()
    geojson_layers = GeojsonLayer.objects.all()
    return render_to_response('map/map.html', {'default_tile_layer': default_tile_layer,
                                               'zoomRange': range(19),
                                               'tile_layers': tile_layers,
                                               'geojson_layers': geojson_layers,
                                               'weight_collections': weight_collections},
                              context_instance=RequestContext(request))


def legend(request):
    """
    Legend items for given zoom.
    """
    zoom = int(request.GET['zoom'])
    legenditems = Legend.objects.all()[0].legend_items(zoom)
    return TemplateResponse(request, 'map/legend.html', {'zoom': zoom, 'legenditems': legenditems})


def routingparams(request):
    """
    Route parameters and preferences template for given id.
    """
    try:
        template_id = request.GET['template_id']
        weight_collection = WeightCollection.objects.get(pk=template_id)
    except KeyError:
        # template not found
        weight_collection = WeightCollection.objects.all()[0]
    return TemplateResponse(request, 'map/routingparams.html', {'weight_collection': weight_collection})


def exportmap(request):
    """
    Export map, response is PNG image.
    """
    try:
        zoom = int(request.POST['export-zoom'])
        bounds = request.POST['export-bounds'].replace('(', '').replace(')', '')
    except KeyError:
        # no zoom posted
        return render_to_response('map/map.html', {},
                                  context_instance=RequestContext(request))
    else:
        map_title = request.POST['map-title']
        if map_title.startswith('orlice_'):
            try:
                side = map_title.replace('orlice_', '')[0]
                if side in ('n', 'e', 's', 'w'):
                    orientation = side
                else:
                    orientation = 'n'
            except IndexError:
                orientation = 'n'
        else:
            orientation = 'n'
        tile_layer = TileLayer.objects.get(slug='mtb-map')
        bottom = float(bounds.split(',')[1])
        top = float(bounds.split(',')[3])
        left = float(bounds.split(',')[0])
        right = float(bounds.split(',')[2])
        zoom = int(zoom)
        map_x, map_y = get_image_size(zoom, top, left, bottom, right)
        if map_x * map_y > 6000000:
            message = _('Sorry, requested image is too big. Try export of smaller area.')
            return render_to_response('error.html', {'message': message}, context_instance=RequestContext(request))
        gap = 5
        line = None
        if 'export-line-check' in request.POST:
            raw_line = request.POST['export-line']
            points = []
            if len(raw_line):
                for part in raw_line.split('),'):
                    latlng = part.replace('LatLng(', '').replace(')', '').split(',')
                    point = Point(float(latlng[1]), float(latlng[0]))
                    points.append(point)
                if len(points) > 1:
                    line = LineString(points).geojson

        highres = 'export-highres' in request.POST
        map_im = map_image(zoom, left, bottom, right, top, line, orientation, highres)

        if 'export-legend' in request.POST:
            legend_obj = Legend.objects.all()[0]
            legend_im = legend_image(legend_obj, zoom, gap, 'side', map_im.size[1], highres)
        else:
            # export-legend not checked
            legend_im = Image.new('RGBA', (0, 0), 'white')

        if 'export-scale' in request.POST:
            scalebar_im = scalebar_image(zoom, (top+bottom)/2, highres)
        else:
            # export-scale not checked
            scalebar_im = Image.new('RGBA', (0, 0), 'white')

        if 'export-imprint' in request.POST:
            imprint_im = imprint_image(tile_layer.attribution, map_im.size[0], 20, 12, highres)
        else:
            # export-imprint not checked
            imprint_im = Image.new('RGBA', (0, 0), 'white')

        if len(map_title) > 0 and not map_title.startswith('orlice_'):
            name_im = name_image(map_title, map_im.size[0])
        else:
            name_im = Image.new('RGBA', (0, 0), 'white')
        im_height = map_im.size[1] + name_im.size[1] + scalebar_im.size[1] + imprint_im.size[1]
        im_width = map_im.size[0] + legend_im.size[0]

        y_base = 0
        im = Image.new('RGBA', (im_width, im_height), 'white')
        im.paste(name_im, (map_im.size[0]/2 - name_im.size[0]/2, 0))
        y_base += name_im.size[1]
        im.paste(scalebar_im, (map_im.size[0]/2 - scalebar_im.size[0]/2, y_base))
        y_base += scalebar_im.size[1]
        im.paste(map_im, (0, y_base))
        im.paste(legend_im, (map_im.size[0], y_base))
        y_base += map_im.size[1]
        im.paste(imprint_im, (map_im.size[0]/2 - imprint_im.size[0]/2, y_base))

        response = HttpResponse(content_type='image/png')
        response['Content-Disposition'] = 'attachment; filename="map.png"'
        im.save(response, 'png')
        return response


def altitudeprofile(request):
    """
    Return altitude profile image.
    """
    try:
        params = request.POST['profile-params']
    except KeyError:
        # no points posted
        return render_to_response('map/map.html', {},
                                  context_instance=RequestContext(request))
    else:
        points = []
        if len(params):
            for part in params.split('),'):
                latlng = part.replace('LatLng(', '').replace(')', '').split(',')
                point = [float(latlng[0]), float(latlng[1])]
                points.append(point)
            if len(points) == 1:
                res = height(points[0])
            else:
                altitude_profile = AltitudeProfile(points)
                if altitude_profile.status < 0:
                    res = -10000
                else:
                    im = altitude_profile.png_profile()
                    response = HttpResponse(content_type='image/png')
                    im.save(response, 'png')
                    response['Content-Disposition'] = 'attachment; filename="altitudeprofile.png"'
                    return response
            if res <= -10000:
                message = _('Sorry, we do not have height data for the area that you have requested.')
                return render_to_response('error.html', {'message': message}, context_instance=RequestContext(request))
            else:
                return render_to_response('map/height.html', {'height': res}, context_instance=RequestContext(request))
        else:
            message = _('You have not set any point.')
            return render_to_response('error.html', {'message': message}, context_instance=RequestContext(request))


def creategpx(request):
    """
    Return GPX file for given points.
    """
    try:
        params = request.POST['profile-params']
    except KeyError:
        # no points posted
        message = _('No route parameters posted.')
        return render_to_response('error.html', {'message': message},
                                  context_instance=RequestContext(request))
    else:
        points = []
        if len(params):
            for part in params.split('),'):
                latlng = part.replace('LatLng(', '').replace(')', '').split(',')
                point = [float(latlng[0]), float(latlng[1])]
                points.append(point)
            gpx = create_gpx(points)
            response = HttpResponse(content_type='application/xml')
            response['Content-Disposition'] = 'attachment; filename="line.gpx"'
            response.write(gpx)
            return response
        else:
            message = _('You have not set any point.')
            return render_to_response('error.html', {'message': message}, context_instance=RequestContext(request))


def getheight(request):
    """
    Returns height above sea level at given coordinates.
    """
    get_value = request.GET['profile-point']
    latlng = get_value.replace('LatLng(', '').replace(')', '').split(',')
    point = [float(latlng[0]), float(latlng[1])]
    point_height = height(point)
    return HttpResponse(point_height, content_type='text/html')


def findroute(request):
    """
    Search for route between multiple points.
    """
    try:
        params = json.loads(request.POST['params'])
        line = request.POST['routing-line']
    except KeyError:
        # invalid route points
        return render_to_response('map/map.html', {},
                                  context_instance=RequestContext(request))
    else:
        points = line_string_to_points(line)
        multiroute = MultiRoute(points, params)
        status = multiroute.find_multiroute()
        geojson = multiroute.geojson()
        logger.debug('Length:', multiroute.length, status, multiroute.search_index())
        return HttpResponse(json.dumps(geojson), content_type='application/json')


def gettemplate(request):
    """
    Create JSON file with route parameters.
    """
    try:
        params = json.loads(request.POST['params'])
    except KeyError:
        # missing params
        message = _('No route parameters posted.')
        return render_to_response('error.html', {'message': message},
                                  context_instance=RequestContext(request))
    else:
        routeparams = RouteParams(params)
        json_params = routeparams.dump_params()
        response = HttpResponse(content_type='text/plain')
        response['Content-Disposition'] = 'attachment; filename="template.json"'
        response.write(json.dumps(json_params, indent=4, sort_keys=True))
        return response


def getjsondata(request):
    """
    Returns GeoJSON feature collection for given bounding box and layer id.
    """
    try:
        bounds = json.loads(request.GET['bounds'])
    except (KeyError, JSONDecodeError):
        # invalid bounds
        bounds = [-0.001, -0.001, 0.001, 0.001]
    try:
        layer_slug = request.GET['slug']
        layer = GeojsonLayer.objects.get(slug=layer_slug)
    except (KeyError, GeojsonLayer.DoesNotExist):
        # unknown layer
        return HttpResponse(None, content_type='application/json')
    geojson = layer.geojson_feature_collection(bounds)
    return HttpResponse(json.dumps(geojson), content_type='application/json')


def set_language(request, lang):
    redirect_url = request.META.get('HTTP_REFERER', None)
    if not redirect_url:
        redirect_url = '/'
    response = HttpResponseRedirect(redirect_url)
    if request.method == 'GET':
        lang_code = lang
        if lang_code and translation.check_for_language(lang_code):
            if hasattr(request, 'session'):
                request.session['django_language'] = lang_code
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang_code)
    return response
