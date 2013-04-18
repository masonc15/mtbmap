#!/usr/bin/python
# -*- coding: utf-8 -*-

import simplejson as json
from map.models import WeightCollection, WeightClass, Weight
#from map.updateroutingdata import to_float

def import_json_template(filename):
    """Import weight classes and their parameters into the database."""
    file = open(filename, 'r')
    json_template = json.loads(file.read())
    file.close()
    name = json_template['name']
    oneway = json_template['oneway']
    vehicle = json_template['vehicle']
    if WeightCollection.objects.filter(name=name).count():
        WeightCollection.objects.filter(name=name)[0].delete()
    weight_collection = WeightCollection(name=name, vehicle=vehicle)
    weight_collection.save()
    class_order = 0
    for c in json_template['classes']:
        weight_class = WeightClass()
        weight_class.classname = c['name']
        weight_class.collection = weight_collection
        weight_class.use = c['use']
        weight_class.order = class_order
        if 'max' in c:
            weight_class.max = c['max']
        if 'min' in c:
            weight_class.min = c['min']
        if 'prefer' in c:
            weight_class.prefer = c['prefer']
        weight_class.save()
        if 'features' in c:
            feature_order = 0
            for feature in c['features']:
                w = Weight(classname=weight_class, feature=feature['name'], preference=feature['value'], order=feature_order)
                if 'visible' in feature:
                    w.visible = feature['visible']
                w.save()
                feature_order +=1
        class_order += 1
