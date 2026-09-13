#!/bin/bash
# BioCore onboarding, end to end, in curl — every call a real client makes.
#
#   bash scripts/curl_flow.sh
#
# Step 8 is the one that issues the credential. With the placeholder image below it comes back
# 422 CAPTURE_REFUSED, because the face service runs its own quality gate and refuses a capture
# it cannot enrol from. The `reason` says which:
#
#   MEDIA_CORRUPT      the bytes are not a decodable image ("QUJD" is the text "ABC")
#   QUALITY_FAILED     a real photo, but too blurry or too small
#   LANDMARK_UNSTABLE  a face was found but could not be measured reliably
#
# To get a credential, put a real webcam capture in step 8:
#   IMAGE=$(cat my-selfie.b64)   # "data:image/jpeg;base64,..."
#
# Two things this script needs running: the API on :8080 and Redis on :6379 (it reads the
# one-time code from there, standing in for the email a real person would receive).
API=http://127.0.0.1:8080/api/v1
REDIS="C:/Users/DELL/tools/redis/redis-cli.exe"
ORG="CURL-$RANDOM"
ADMIN="ops_$RANDOM@acmemfg.co.in"
PERSON="asha_$RANDOM@mailbox.co.in"
PW='Str0ng-Ops-Passw0rd!'
csrf() { grep -i csrf "$1" | awk '{print $NF}'; }

echo "1. create the organisation"
curl -s -X POST $API/admin/tenants -H "Content-Type: application/json" \
  -d "{\"name\":\"Acme\",\"org_code\":\"$ORG\",\"vertical\":\"office\",\"plan\":\"starter\",
       \"admin_email\":\"$ADMIN\",\"admin_password\":\"$PW\",\"admin_name\":\"Ops\"}" \
  -o /dev/null -w "   -> %{http_code}\n"

echo "2. admin signs in"
curl -s -c /tmp/admin.txt -X POST $API/auth/login -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN\",\"password\":\"$PW\"}" -o /dev/null -w "   -> %{http_code}\n"

echo "3. person requests a sign-in code"
curl -s -X POST $API/person/auth/otp/request -H "Content-Type: application/json" \
  -d "{\"email\":\"$PERSON\"}" -o /dev/null -w "   -> %{http_code}\n"
OTP=$("$REDIS" -p 6379 get "otp:$PERSON")
echo "   code from redis: $OTP"

echo "4. person signs in"
curl -s -c /tmp/p.txt -X POST $API/person/auth/otp/verify -H "Content-Type: application/json" \
  -d "{\"email\":\"$PERSON\",\"otp\":\"$OTP\"}" -o /dev/null -w "   -> %{http_code}\n"

echo "5. person gives their details"
curl -s -b /tmp/p.txt -c /tmp/p.txt -X PATCH $API/person/me \
  -H "Content-Type: application/json" -H "X-CSRF-Token: $(csrf /tmp/p.txt)" \
  -d '{"first_name":"Asha","last_name":"Rao","gender":"female","date_of_birth":"1994-07-12"}' \
  -o /dev/null -w "   -> %{http_code}\n"

echo "6. person joins the organisation"
MID=$(curl -s -b /tmp/p.txt -c /tmp/p.txt -X POST $API/person/businesses/join \
  -H "Content-Type: application/json" -H "X-CSRF-Token: $(csrf /tmp/p.txt)" \
  -d "{\"org_code\":\"$ORG\"}" | grep -o '"membership_id":"[^"]*' | cut -d'"' -f4)
echo "   membership: $MID"

echo "7. consent + start verification"
curl -s -b /tmp/p.txt -c /tmp/p.txt -X POST $API/person/verify/$MID/start \
  -H "Content-Type: application/json" -H "X-CSRF-Token: $(csrf /tmp/p.txt)" \
  -d '{"consents":["identity_verification","government_data_processing","live_face_capture",
       "face_to_government_match","entry_template_creation","entry_authentication"]}' \
  -o /dev/null -w "   -> %{http_code}\n"

echo "8. submit the selfie  <-- the one that returns 422"
curl -s -b /tmp/p.txt -c /tmp/p.txt -X POST $API/person/verify/$MID/complete \
  -H "Content-Type: application/json" -H "X-CSRF-Token: $(csrf /tmp/p.txt)" \
  -d '{"reference":"'"$MID"'","image":"data:image/jpeg;base64,QUJD"}' \
  -w "\n   -> %{http_code}\n"
