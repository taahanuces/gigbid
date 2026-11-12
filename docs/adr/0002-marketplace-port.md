# ADR 0002: One marketplace port

Status: accepted

All marketplace reads and writes use a typed `MarketplacePort`. GigSim and live Upwork implement this
port. Graph nodes cannot import adapter modules. This makes the November policy change and live-mode
switch configuration concerns instead of graph rewrites.

