# Copyright (c) The InfoOrgBench authors.
# Licensed under the MIT License.
"""Frozen pure helpers from the historical organization harness; see helper-provenance.json."""

from collections import Counter, defaultdict

from itertools import combinations

import json

import math

import re

def descendant_sets(rows):
    groups = defaultdict(set)
    for row in rows:
        for depth in range(1, len(row["path"]) + 1):
            groups[tuple(row["path"][:depth])].add(row["id"])
    return {frozenset(members) for members in groups.values() if 1 < len(members) < len(rows)}

def set_agreement(predicted, expected):
    correct = len(predicted & expected)
    return {"precision": correct / len(predicted) if predicted else None,
            "recall": correct / len(expected) if expected else None,
            "f1": 2 * correct / (len(predicted) + len(expected)) if predicted or expected else None,
            "predicted": len(predicted), "reference": len(expected), "matched": correct}

def partition_diagnostics(rows,gold):
    def groups(records):
        membership={};partitions=defaultdict(set)
        for row in records:
            identity=row['id'];path=row['path']
            if not isinstance(identity,str) or identity in membership or not isinstance(path,list) or any(not isinstance(part,str) for part in path):
                raise ValueError('Invalid or duplicated partition record')
            membership[identity]=tuple(path);partitions[tuple(path)].add(identity)
        return membership,partitions
    actual_by_id,actual=groups(rows);gold_by_id,expected=groups(gold)
    if not gold_by_id or actual_by_id.keys()!=gold_by_id.keys():raise ValueError('Grouping comparison requires identical nonempty item sets')
    predicted_pairs={tuple(sorted(pair)) for group in actual.values() for pair in combinations(group,2)}
    reference_pairs={tuple(sorted(pair)) for group in expected.values() for pair in combinations(group,2)}
    correct=len(predicted_pairs&reference_pairs)
    count=len(gold_by_id);merge_bits=0;split_bits=0;per_file={};overlaps=[]
    for path,members in actual.items():
        intersections=Counter(gold_by_id[identity] for identity in members)
        for reference_path,overlap in intersections.items():
            merge_bits+=overlap/count*math.log2(len(members)/overlap)
            split_bits+=overlap/count*math.log2(len(expected[reference_path])/overlap)
            overlaps.append({'actual_path':list(path),'reference_path':list(reference_path),'count':overlap})
        for identity in members:
            reference_members=expected[gold_by_id[identity]];overlap=len(members&reference_members)
            status='exact' if members==reference_members else 'pure_split' if members<reference_members else 'mixed_merge' if reference_members<members else 'mixed_split'
            per_file[identity]={'status':status,'actual_path':list(path),'reference_path':list(gold_by_id[identity]),
                'correct_peers':overlap-1,'foreign_peers':len(members-reference_members),
                'missing_peers':len(reference_members-members),'group_precision':overlap/len(members),
                'group_recall':overlap/len(reference_members)}
    precision=correct/len(predicted_pairs) if predicted_pairs else None
    recall=correct/len(reference_pairs) if reference_pairs else None
    bcubed_precision=sum(row['group_precision'] for row in per_file.values())/count
    bcubed_recall=sum(row['group_recall'] for row in per_file.values())/count
    reference_entropy=-sum(len(group)/count*math.log2(len(group)/count) for group in expected.values())
    actual_entropy=-sum(len(group)/count*math.log2(len(group)/count) for group in actual.values())
    homogeneity=1-merge_bits/reference_entropy if reference_entropy else 1
    completeness=1-split_bits/actual_entropy if actual_entropy else 1
    return {'items':count,'pair_counts':{'true_positive':correct,'false_positive':len(predicted_pairs-reference_pairs),
            'false_negative':len(reference_pairs-predicted_pairs)},
        'pair_precision':precision,'pair_recall':recall,
        'pair_f1':2*correct/(len(predicted_pairs)+len(reference_pairs)) if predicted_pairs or reference_pairs else None,
        'bcubed':{'precision':bcubed_precision,'recall':bcubed_recall,
                  'f1':2*bcubed_precision*bcubed_recall/(bcubed_precision+bcubed_recall)},
        'merge_bits':merge_bits,'split_bits':split_bits,'variation_information_bits':merge_bits+split_bits,
        'homogeneity':max(0,homogeneity),'completeness':max(0,completeness),
        'per_file':per_file,'status_counts':dict(Counter(row['status'] for row in per_file.values())),
        'contingency':overlaps,'predicted_group_count':len(actual),'reference_group_count':len(expected),
        'scope':'Post-hoc partition diagnostics. Mixing is H(reference|output); splitting is H(output|reference), in bits. Lower is better. B-cubed includes self credit. Parent labels and common wrappers are ignored; no source metadata enters model input.'}

def hierarchy_triplets(rows,gold):
    actual={row['id']:row['path'] for row in rows};reference={row['id']:row['path'] for row in gold}
    if len(actual)!=len(rows) or len(reference)!=len(gold) or not actual or actual.keys()!=reference.keys():raise ValueError('Triplet item sets differ or contain duplicates')
    def prefix_length(left,right):
        return next((index for index,(first,second) in enumerate(zip(left,right)) if first!=second),min(len(left),len(right)))
    def pair_depths(paths):
        return {tuple(sorted(pair)):prefix_length(paths[pair[0]],paths[pair[1]]) for pair in combinations(paths,2)}
    actual_depths=pair_depths(actual);reference_depths=pair_depths(reference);counts=Counter();levels=defaultdict(Counter)
    for triple in combinations(sorted(reference),3):
        pairs=list(combinations(triple,2));expected=[reference_depths[pair] for pair in pairs]
        deepest=max(expected)
        if expected.count(deepest)!=1:continue
        observed=[actual_depths[pair] for pair in pairs];maximum=max(observed)
        status='unresolved' if observed.count(maximum)!=1 else 'preserved' if observed.index(maximum)==expected.index(deepest) else 'contradicted'
        counts[status]+=1;levels[str(deepest)][status]+=1
    total=sum(counts.values())
    return {'counts':dict(counts),'resolved_reference_triplets':total,'preserved_fraction':counts['preserved']/total if total else None,
        'by_reference_folder_depth':{level:{'counts':{status:values[status] for status in ['preserved','unresolved','contradicted']},
            'total':sum(values.values()),'preserved_fraction':values['preserved']/sum(values.values()),
            'contradicted_fraction':values['contradicted']/sum(values.values())} for level,values in sorted(levels.items())},
        'scope':'For each reference-resolved triple, compare which file pair has the deepest shared folder ancestor. Pure refinements can preserve coarse ancestry. Report unresolved and contradicted separately; coarse reference branches can dominate counts.'}

def validate_descriptive_path(path):
    if not isinstance(path,list) or not 1<=len(path)<=4 or any(
        not isinstance(part,str) or not part.strip() or re.fullmatch(r'[A-Z][1-9][0-9]*',part) or part.endswith('.txt') for part in path):
        raise ValueError('Invalid descriptive folder path')

def parse_layout(text,identifiers):
    def unique(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise ValueError('Duplicate JSON key')
            value[key]=item
        return value
    value=json.loads(text,object_pairs_hook=unique)
    if not isinstance(value,dict) or set(value)!={'folders'} or not isinstance(value['folders'],list):
        raise ValueError('Expected folders array')
    rows=[]
    seen=set()
    for folder in value['folders']:
        if not isinstance(folder,dict) or set(folder)!={'folder_path','file_ids'}:
            raise ValueError('Expected folder_path and file_ids')
        path=folder['folder_path']
        validate_descriptive_path(path)
        members=folder['file_ids']
        if not isinstance(members,list) or not members:raise ValueError('Expected nonempty file_ids')
        for identity in members:
            if not isinstance(identity,str) or identity not in identifiers or identity in seen:
                raise ValueError('Duplicate or unknown file ID')
            rows.append({'id':identity,'path':path})
            seen.add(identity)
    if seen!=set(identifiers):raise ValueError('Missing active file IDs')
    return rows

def pending_records(rows):
    return [row['id'] for row in rows if row['path'] and row['path'][0]=='inbox']

def completion_assessment(actual,integrity,declaration,journal,captured):
    final={row['id']:row['path'] for row in actual};checks=[row for row in journal['operations'] if row['method']=='check_inventory' and row['status']==200]
    latest=checks[-1] if checks else None;response=latest['response'] if latest else {}
    checked={identity:folder['folder_path'] for folder in response.get('folders',[]) for identity in folder['file_ids']}
    checker_current=bool(latest and response.get('inventory_preserved') and not response.get('pending_ids') and checked==final)
    filing=bool(integrity['passed'] and not pending_records(actual))
    return {'filing_complete':filing,'checker_matches_final_state':checker_current,
        'checker_operation':latest['sequence'] if latest else None,
        'contract_passed':filing and declaration and checker_current and not captured.get('unexpected_workspace_entries')}
