#!/usr/bin/env bash
set -euo pipefail

CERT_DIR="${CERT_DIR:-certs}"
DEVICE_NAME="${DEVICE_NAME:-factory-tv-01}"
ORG_NAME="${ORG_NAME:-Example Corp}"
HOST_NAME="${HOST_NAME:-localhost}"
DAYS_VALID="${DAYS_VALID:-365}"

mkdir -p "$CERT_DIR"

echo "Generating demo CA..."
openssl req -x509 -newkey rsa:2048 -days "$DAYS_VALID" -nodes \
  -keyout "${CERT_DIR}/ca.key" \
  -out "${CERT_DIR}/ca.crt" \
  -subj "/CN=Factory Demo CA"

echo "Generating client key + CSR for ${DEVICE_NAME}..."
client_cnf="$(mktemp)"
cat > "${client_cnf}" <<EOF
[ req ]
distinguished_name = dn
prompt = no
req_extensions = req_ext

[ dn ]
CN = ${DEVICE_NAME}
O = ${ORG_NAME}

[ req_ext ]
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = clientAuth
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = ${DEVICE_NAME}
EOF

openssl req -newkey rsa:2048 -nodes \
  -keyout "${CERT_DIR}/${DEVICE_NAME}.key" \
  -out "${CERT_DIR}/${DEVICE_NAME}.csr" \
  -config "${client_cnf}"

echo "Signing client cert with demo CA..."
openssl x509 -req \
  -in "${CERT_DIR}/${DEVICE_NAME}.csr" \
  -CA "${CERT_DIR}/ca.crt" \
  -CAkey "${CERT_DIR}/ca.key" \
  -CAcreateserial \
  -out "${CERT_DIR}/${DEVICE_NAME}.crt" \
  -days "$DAYS_VALID" \
  -extensions req_ext \
  -extfile "${client_cnf}"

rm -f "${client_cnf}"

echo "Generating server cert for ${HOST_NAME}..."
openssl req -x509 -newkey rsa:2048 -days "$DAYS_VALID" -nodes \
  -keyout "${CERT_DIR}/server.key" \
  -out "${CERT_DIR}/server.crt" \
  -subj "/CN=${HOST_NAME}"

echo ""
echo "Done. Files written to: ${CERT_DIR}"
echo "Client cert: ${CERT_DIR}/${DEVICE_NAME}.crt"
echo "Client key:  ${CERT_DIR}/${DEVICE_NAME}.key"
echo "CA cert:     ${CERT_DIR}/ca.crt"
echo "Server cert: ${CERT_DIR}/server.crt"
