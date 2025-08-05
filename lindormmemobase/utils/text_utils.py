"""
Simple utility functions that don't depend on other modules
to avoid circular imports.
"""

def attribute_unify(attr: str):
    """Unify attribute names by converting to lowercase and replacing spaces with underscores"""
    return attr.lower().strip().replace(" ", "_")