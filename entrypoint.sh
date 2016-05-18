#!/bin/bash
set -e

THIS_DIR="$(cd "$(dirname "$0")"; pwd)"
source "$THIS_DIR/python_env/bin/activate"

if [[ -x "$THIS_DIR/pre-entry.sh" ]]; then
  echo "Sourcing pre-entry script" >&2
  source "$THIS_DIR/pre-entry.sh"
else
  echo "Skipping pre-entry script" >&2
fi

function doc {
  PYTHONPATH="$THIS_DIR:$PYTHONPATH" \
      sphinx-build "$THIS_DIR/docs" "$THIS_DIR/docs-build"
}
function publish {
  cd "$THIS_DIR"
  current_branch="$(git rev-parse --abbrev-ref HEAD)"
  git checkout 'gh-pages'
  git pull origin 'gh-pages'
  git merge -m "Merge branch '$current_branch' into gh-pages" "$current_branch"
  doc
  rm -rf 'docs-build/.doctrees'
  git commit -m 'Update docs' docs-build || true
  git push -u origin gh-pages
  git checkout "$current_branch"
  cd -
}
function pep8_ {
  pep8 "mt_remote"
}
function pylint_ {
  pylint --rcfile "$THIS_DIR/pylint.conf" "mt_remote"
}
function styletest {
  pep8_; pylint_
}
function doctest {
  py.test --doctest-modules -vvrxs "$THIS_DIR/mt_remote"
}
function unittest {
  py.test -vvrxs "$THIS_DIR/tests"
}
function ci {
  styletest; doctest #; unittest
}
function run {
  python -m mt_remote
}

case "$1" in
  doc|styletest|doctest|unittest|ci|run) "$1" ;;
  *) "$@";;
esac
