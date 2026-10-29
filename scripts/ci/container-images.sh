# Images de conteneur des paquets DNF et pacman, utilisées par build-linux-packages.sh et prepare-package-repository.sh.
# Épinglées par version et par digest : une image modifiée sur le registre ne change plus les paquets publiés.
# Pour les rafraîchir, relever la dernière version numérique sur https://hub.docker.com/_/fedora et l'étiquette
# base-AAAAMMJJ.0.N la plus récente sur https://hub.docker.com/_/archlinux avec leur digest, puis relancer les paquets Linux de la CI.
FEDORA_IMAGE="fedora:44@sha256:43b29f65a41eb9c35e1cd5323e3bdf3b655c2357a9f4f1ff2f9c2798e5045d80"
ARCH_IMAGE="archlinux:base-20261025.0.616225@sha256:e82623936fa1a69700b48e98b058df6eaab18b737c27473a7234a40fdecb9413"
