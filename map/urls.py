from django.conf.urls import *

urlpatterns = patterns('map.views',
    url(r'^legend/$', 'legend'),
    url(r'^routingparams/$', 'routingparams'),
    url(r'^exportmap/$', 'exportmap'),
    url(r'^altitudeprofile/$', 'altitudeprofile'),
    url(r'^creategpx/$', 'creategpx'),
    url(r'^getheight/$', 'getheight'),
    url(r'^findroute/$', 'findroute'),
    url(r'^gettemplate/$', 'gettemplate'),
    url(r'^getjsondata/$', 'getjsondata'),
    url(r'^evaluation/$', 'evaluation'),
)