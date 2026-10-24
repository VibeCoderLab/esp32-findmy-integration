"""Select a zone identity by its signed public reference, never by list position."""
from findmy.cloudkit import der
from common import WorkflowError


def select_zone_identity(key_list_der, private_keys):
    if not key_list_der:
        raise WorkflowError('The zone publishes no identity key reference; refusing to guess a key.')
    roots = der.parse_all(key_list_der)
    if len(roots) != 1 or not roots[0].is_universal(der.TAG_SEQUENCE):
        raise WorkflowError('Unknown zone key reference format.')
    published = []
    for entry in roots[0].children():
        parts = entry.children()
        if len(parts) != 2 or parts[0].as_int() != 3 or len(parts[1].as_bytes()) != 32:
            raise WorkflowError('Unsupported zone key reference.')
        published.append(parts[1].as_bytes())
    by_public = {key.public_key().public_numbers().x.to_bytes(32, 'big'): key for key in private_keys}
    matches = {public: by_public[public] for public in published if public in by_public}
    if len(matches) != 1:
        raise WorkflowError('No unique private key matches the published zone identity; stopping.')
    return next(iter(matches.values()))
