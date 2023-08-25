#!/bin/bash

#serve the docs for modification, then git push when ctrl-c recieved on serving

#push docs updates to git
function git_push() {
    git add ../docs ../mdbook
    printf "\nPlease enter commit message: "
    read msg #TODO->check if empty, and if so, print old docs message "automatic update to docs on $(date)" 
    git commit -m "$msg"
    git push
}

#run git_push when ctrl-c received
trap git_push INT
 
#serve the docs at localhost:3000 and open a chrome tab there
google-chrome http://localhost:3000 &
mdbook serve