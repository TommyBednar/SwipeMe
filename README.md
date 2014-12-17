_We are deprecating SwipeMe v1. A port to Rails is in the works. More details to come._

SwipeMe
=======

A marketplace for Pitt dining hall passes.

How To Set Up Your Dev Environment
-----------------------------------

1. Install Vagrant
2. Install Virtualbox
3. Use Git to clone this repo to your machine
4. Navigate to /path/to/repo/you/just/cloned
5. run “vagrant up”
6. The VM is now running! To get inside, type "vagrant ssh"
7. cd to /vagrant
8. To start the development server, `./run.sh`. To deploy, `./deploy.sh`.
    - I needed to tweak my Google security settings at https://www.google.com/settings/security/lesssecureapps
to allow deployment from the command line. Allow "Less Secure Apps" and you should be good to go.
9. You can type `127.0.0.1:8080` in your browser to request the site and `127.0.0.1:8000` to access the admin console.
