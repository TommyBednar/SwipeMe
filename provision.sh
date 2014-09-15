#!/usr/bin/env bash
#The above line specifies what shell this
# script needs to run on.

sudo apt-get update
sudo apt-get -y install unzip

cd /home/vagrant
curl -O https://storage.googleapis.com/appengine-sdks/featured/google_appengine_1.9.10.zip
unzip google_appengine_1.9.10.zip
echo 'export PATH="$PATH:~/google_appengine"' >> ./.bash_profile