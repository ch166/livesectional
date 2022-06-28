#!/bin/bash

# Copy the correct files into /NeoSectional

mkdir -p /NeoSectional

cp *.py /NeoSectional
cp config.ini /NeoSectional

mkdir -p /NeoSectional/data
cp data/airports.json /NeoSectional/data/

mkdir -p /NeoSectional/templates
cp templates/*.html /NeoSectional/templates/

mkdir -p /NeoSectional/logs/
