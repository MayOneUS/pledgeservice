#!/bin/bash -e

function update_it {
    PREFIX=$1
    REMOTE_NAME=$2
    REMOTE_PATH=$3
    REMOTE_BRANCH=$4

    if [[ ! -n $(git remote | grep $REMOTE_NAME) ]]; then
        git remote add $REMOTE_NAME $REMOTE_PATH
    fi

    git fetch $REMOTE_PATH $REMOTE_BRANCH
    git subtree pull --prefix $PREFIX $REMOTE_NAME $REMOTE_BRANCH --squash
}

update_it extern/frontend extern-frontend https://github.com/MayOneUS/common-frontend.git master
