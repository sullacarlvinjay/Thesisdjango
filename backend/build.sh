#!/usr/bin/env bash
# Render runs this at build time, before the service starts.
#
# -o errexit matters more than it looks: without it a failed collectstatic or a
# half-applied migration would still be followed by a "successful" deploy, and
# the breakage would only surface as 500s once traffic arrived.
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Gather CSS/JS into STATIC_ROOT for WhiteNoise to serve.
python manage.py collectstatic --no-input

# Safe to run on every deploy; Django skips migrations already applied.
python manage.py migrate

# A migrated database is still an empty one: no scholarships for students to
# apply to, and no account anyone can sign in with. Render's free plan has no
# shell, so createsuperuser cannot be run by hand — this reads the office
# passwords from the environment instead. Idempotent, and it never overwrites
# the password of an account that already exists.
python manage.py bootstrap

# Configuration that would otherwise fail quietly once the site is live. Nothing
# here stops the deploy: the warnings are for things the site survives without
# but nobody would notice were missing. See api/checks.py.
python manage.py check

# settings.py only checks the SUPABASE_S3_* variables are set, not that they
# work: a wrong region or a mistyped secret starts the site fine and fails the
# first time a student uploads something. One round trip against the bucket
# turns that into a build failure with the cause named. Does nothing when
# uploads are on the local filesystem.
python manage.py check_storage
