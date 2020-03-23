#!/bin/bash

#serve the docs for modification, then git push when ctrl-c recieved on serving

#push docs updates to git
function git_push() {
    git add ../docs ../mdbook
    printf "\nPlease enter commit message: "
    read msg
    git commit -m "$msg. automatic update to docs on $(date)" #TODO->figure out how to let this write my own commit message
    git push
}

#run git_push when ctrl-c received
trap git_push INT
 
#serve the docs at localhost:3000 and open a chrome tab there
google-chrome http://localhost:3000 &
mdbook serve