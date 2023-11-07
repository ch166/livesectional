#!/bin/bash

# Copy the correct files into /NeoSectional

mkdir -p /NeoSectional

cp *.py /NeoSectional
cp config.ini /NeoSectional
cp requirements.txt /NeoSectional

mkdir -p /NeoSectional/data
cp data/airports.json /NeoSectional/data/

mkdir -p /NeoSectional/templates
cp templates/*.html /NeoSectional/templates/

mkdir -p /NeoSectional/static
rsync -rav --relative static/ /NeoSectional/

mkdir -p /NeoSectional/logs/

cp livemap.service /etc/systemd/system/livemap.service
systemctl daemon-reload
#systemctl restart livemap

echo -e "Try\nsystemctl restart livemap ; systemctl status livemap"
