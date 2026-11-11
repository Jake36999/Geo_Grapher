"""Backend edge classification (edge-chromatics-v1, master G9). The `violation` family is client-side only."""
HIERARCHY_SUBTYPES=frozenset({'inherits','implements','imports','imports_from'})
DOCUMENTARY_FAMILIES={'rationale_for':'doc_rationale','documents':'doc_describes','discusses':'doc_describes','cites':'doc_cites'}

def classify_relationship(family,subtype,resolution_status):
    kind='hierarchy' if subtype in HIERARCHY_SUBTYPES else 'call_or_data'
    if family=='runtime':status='observed'
    elif family=='expected':status='expected_only'
    elif resolution_status in ('candidate','unresolved'):status='candidate'
    else:status='exact'
    return kind,status

def classify_documentary(role):
    return DOCUMENTARY_FAMILIES.get(role,'doc_describes')
