#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
default configuration
'''

configs = {
    'debug':True,
    'db':{
        'host':'127.0.01',
        'post':3306,
        'user':'www-data',
        'password':'www-data',
        'db':'awesome'
    },
    'session':{
        'secret':'Awesome'
    }
}