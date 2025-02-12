#!/usr/bin/env bash

source "$(dirname "$0")"/utils.sh

# Create a self signed SSL cert for this host
#
# Install as server_cert.{crt|key}
# 


DOMAIN=$(hostname -d)
HOSTNAME=$(hostname -s)
LOCALIP=$(hostname -I | cut -d ' ' -f 1)

FNAME=$DATADIR/$HOSTNAME.$DOMAIN
SRVR_CRT=$DATADIR/server_cert.crt
SRVR_KEY=$DATADIR/server_cert.key

if [ -f "$FNAME.crt" ]; then
	NOT_AFTER=$(openssl x509 -in $SRVR_CRT -text -noout | grep 'Not After'| cut -c 25-)
	SECS_LEFT_MATH="$(date -d "$NOT_AFTER" +%s) - $(date -d "now" +%s)"
	SECS_LEFT="$(expr $SECS_LEFT_MATH)"
	DAYS_LEFT="$(expr $SECS_LEFT / 86400)"
	echo "Cert days remaining: $DAYS_LEFT" | logger -t livemap-ssl-check
	if (( "$DAYS_LEFT" > 5 )); then
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
  -keyout "$FNAME.key" \
  -out "$FNAME.crt" \
  -subj "/CN=$DOMAIN" \
  -addext "subjectAltName=DNS:$HOSTNAME,DNS:$DOMAIN,DNS:*.$DOMAIN,IP:$LOCALIP"
error_check $?


ln -sf "$FNAME.crt" "$SRVR_CRT"
error_check $?
ln -sf "$FNAME.key" "$SRVR_KEY"
error_check $?

exit 0
