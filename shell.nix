{pkgs ? import <nixpkgs> { }}: pkgs.mkShell {
  packages = [
    (pkgs.python3.withPackages(p: [p.requests]))
    pkgs.ty
    pkgs.ruff
  ];
}
