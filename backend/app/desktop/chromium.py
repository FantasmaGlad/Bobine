"""Options Chromium d'un kiosque sans accès aux services de l'éditeur."""

OFFLINE_FLAGS = (
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-sync",
    "--disable-domain-reliability",
    "--disable-client-side-phishing-detection",
    "--no-pings",
    "--disable-features=Translate,OptimizationHints,MediaRouter,AutofillServerCommunication",
)
