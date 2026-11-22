(
  set -euo pipefail
  cd ~/comp5355/downloads
  printf '%s  %s\n' \
    'a090046b2d24901eb8dca4d370c28991299e8c7cfb698b44e09ce809b1ff20b4' \
    'json-c-0.18.tar.gz' | sha256sum -c -

  mkdir -p ~/comp5355/sources
  mkdir ~/comp5355/sources/json-c-0.18
  tar -xzf json-c-0.18.tar.gz \
    -C ~/comp5355/sources/json-c-0.18 \
    --strip-components=1

  cd ~/comp5355/sources/json-c-0.18
  sed -n '1,14p' CMakeLists.txt
  sed -n '15,35p' json_c_version.h

  for file in arraylist.c debug.c json_c_version.c json_object.c \
    json_object_iterator.c json_tokener.c json_util.c json_visit.c \
    linkhash.c printbuf.c random_seed.c strerror_override.c \
    json_pointer.c json_patch.c; do
    test -s "$file"
  done
  for file in json_object.h json_tokener.h json_pointer.h json_patch.h \
    json.h.cmakein cmake/config.h.in cmake/json_config.h.in COPYING; do
    test -s "$file"
  done

  printf '14个预定C文件及必要头、配置模板和许可检查通过。\n'
  sed -n '1,22p' COPYING
)
