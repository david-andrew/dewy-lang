#!/bin/bash

function git_push() {
    cd ..
    git add .
    git commit -m "automatic update to docs on $(date)"
    git push
    cd mdbook
}

trap git_push INT
 
google-chrome http://localhost:3000 &
mdbook serve

#this runs the mdbook serve, and then when that is terminated, runs git commit
#trap the_following_line SIGINT
#mdbook serve
# cd .. && git add . && git commit -m "automatic update to docs on $(date)" && git push && cd mdbook
