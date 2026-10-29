# Images de conteneur des paquets DNF et pacman, utilisées par build-linux-packages.sh et prepare-package-repository.sh.
# Épinglées par version et par digest : une image modifiée sur le registre ne change plus les paquets publiés.
# Pour les rafraîchir, relever la dernière version numérique sur https://hub.docker.com/_/fedora et l'étiquette
# base-AAAAMMJJ.0.N la plus récente sur https://hub.docker.com/_/archlinux avec leur digest, puis relancer les paquets Linux de la CI.
FEDORA_IMAGE="fedora:44@sha256:43b29f65a41eb9c35e1cd5323e3bdf3b655c2357a9f4f1ff2f9c2798e5045d80"
ARCH_IMAGE="archlinux:base-20261025.0.616225@sha256:e82623936fa1a69700b48e98b058df6eaab18b737c27473a7234a40fdecb9413"

# Images des tests négatifs du plancher glibc (scripts/ci/test-glibc-floor.sh) : distributions annoncées autrefois, dont la glibc
# est inférieure à packaging/common/MIN_GLIBC (Debian 12 : 2.36, Ubuntu 22.04 : 2.35, AlmaLinux 9 comme RHEL 9 : 2.34).
# Épinglées par version et par digest de l'index multi-architecture (le même digest sert sur les runners x86_64 et arm64).
# Rafraîchir : https://hub.docker.com/_/debian (dernière 12.x), https://hub.docker.com/_/ubuntu (étiquette 22.04),
# https://hub.docker.com/_/almalinux (dernière 9.x datée). Ne jamais passer à une version dont la glibc atteint le plancher.
DEBIAN12_IMAGE="debian:12.15@sha256:d74df7598108a173a621eda4d58a2adbf850b2d9a9d81bc2cca1a6c21174a880"
UBUNTU2204_IMAGE="ubuntu:22.04@sha256:076e7bf82319619f28dd0aa9c02ab34b055ad37100395b4f49a2ffba04fb5e11"
ALMA9_IMAGE="almalinux:9.8-20261027@sha256:245f8aab832fe800aa42bdab5fad75ebbd8e0b4c9f24820a83c638b177857ae2"

# Pas d'image Arch Linux officielle en aarch64 : archlinux sur Docker Hub n'est publiée qu'en amd64 ; Arch Linux ARM est un projet
# distinct, sans image officielle. Le paquet Arch aarch64 ne passe donc que les contrôles d'archive (--no-install), jamais
# une installation. Une image tierce épinglée par digest serait une confiance supplémentaire : non retenue.
