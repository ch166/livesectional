#!/bin/bash

source $(dirname "$0")/utils.sh

# Create a self signed SSL cert for this host
#
# 


DOMAIN="$1"
if [ -z "$DOMAIN" ]; then
  echo "Usage: $(basename $0) <domain>"
  exit 1
fi

HOSTNAME=$(hostname -s)
LOCALIP=$(hostname -I | cut -d ' ' -f 1)

# 
subj="
C=US
ST=OR
O=METAR
localityName=
commonName=$DOMAIN
organizationalUnitName=LiveSectional Map
emailAddress=
"
SSL_DIR=$DATADIR
FNAME=$DATADIR/$HOSTNAME-$DOMAIN

if [ -f $FNAME.crt ]; then
	NOT_AFTER=$(openssl x509 -in $FNAME.crt -text -noout | grep 'Not After'| cut -c 25-)
	DAYS_LEFT_MATH="( $(date -d "$NOT_AFTER" +%s)  -  $(date -d "now" +%s) )/86400 "
	DAYS_LEFT="$(echo $DAYS_LEFT_MATH | bc)"
	if (( $DAYS_LEFT > 5 )); then
		# More than 5 days remaining on validity of cert
		# exiting
		exit 0
	fi
fi


echo "Creating certificate for $DOMAIN; creating $FNAME.{crt|key}"

openssl req \
  -x509 \
  -newkey ec \
  -pkeyopt ec_paramgen_curve:secp384r1 \
  -days 180 \
  -nodes \
  -keyout $FNAME.key \
  -out $FNAME.crt \
  -subj "/CN=$DOMAIN" \
  -addext "subjectAltName=DNS:$HOSTNAME,DNS:$DOMAIN,DNS:*.$DOMAIN,IP:$LOCALIP"


ln -sf $FNAME.crt $DATADIR/server_cert.crt
ln -sf $FNAME.key $DATADIR/server_cert.key

# Generate the CSR
error_check $?
