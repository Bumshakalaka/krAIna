This is a copy of the original **klembord** package: https://github.com/grahampc/klembord.

The package uses **stopit**, which relies on `pkg_resources` from `setuptools`. Since `pkg_resources` is deprecated and will be removed, this causes issues.

A fixed version of **stopit** is available as **stopit2**: https://github.com/spraakbanken/stopit2.

Because the original **stopit** package is no longer maintained, I copied it and modified only the import statements to remove the deprecated functions. This allows the package to run on Python 3.11 and above without any warnings.