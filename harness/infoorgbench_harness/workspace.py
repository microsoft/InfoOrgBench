# Copyright (c) The InfoOrgBench authors.
# Licensed under the MIT License.
import copy
import hashlib
import json
from pathlib import Path
import re


def schema(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


TOOLS = [
    {'type': 'function', 'name': 'list_files', 'description': 'List current record locations and original public format/anchor metadata. Does not return record text.',
     'parameters': schema({'start_at': {'type': 'integer', 'minimum': 0}, 'max_results': {'type': 'integer', 'minimum': 1, 'maximum': 200}})},
    {'type': 'function', 'name': 'read_file', 'description': 'Read exact record text by ID, with character offset/length pagination. Public metadata and next_offset are included.',
     'parameters': schema({'file_id': {'type': 'string'}, 'offset': {'type': 'integer', 'minimum': 0}, 'length': {'type': 'integer', 'minimum': 1, 'maximum': 100000}})},
    {'type': 'function', 'name': 'search_files', 'description': 'Find literal case-insensitive text in public records. Returns snippets only; read_file retrieves complete evidence.',
     'parameters': schema({'query': {'type': 'string'}, 'max_results': {'type': 'integer', 'minimum': 1, 'maximum': 40}})},
    {'type': 'function', 'name': 'move_files', 'description': 'Move selected record IDs to a descriptive folder path, creating folders when needed. Unmentioned records and every body stay unchanged.',
     'parameters': schema({'file_ids': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1},
                           'folder_path': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 1, 'maxItems': 4}})},
    {'type': 'function', 'name': 'check_inventory', 'description': 'Check actual file preservation and pending inbox IDs; return the complete actual ID/path mapping. Does not expose reference quality.',
     'parameters': schema({})},
]


def content_hash(content):
    return hashlib.sha256(content).hexdigest()


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Integer outside the allowed range')
    return value


def tool_schemas(search_max_results=40):
    maximum = integer(search_max_results, 1, 200)
    tools = copy.deepcopy(TOOLS)
    for tool in tools:
        if tool['name'] == 'search_files':
            tool['parameters']['properties']['max_results']['maximum'] = maximum
    return tools


def valid_folder(parts):
    if not isinstance(parts, list) or not 1 <= len(parts) <= 4:
        raise ValueError('Use one to four folder components')
    for part in parts:
        if (not isinstance(part, str) or not part.strip() or len(part) > 100
                or part in {'.', '..'} or part.endswith((' ', '.'))
                or re.search(r'[<>:"/\\|?*\x00-\x1f]', part)
                or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part)):
            raise ValueError('Unsafe or nonportable folder component')
    return parts


class Workspace:
    def __init__(self, root, records, *, search_max_results=40):
        self.root = self._validated_root(root)
        self._bind_records(records)
        self.search_max_results = integer(search_max_results, 1, 200)
        self.root.mkdir(parents=True, exist_ok=False)
        (self.root / 'inbox').mkdir()
        for row in self.records:
            (self.root / 'inbox' / (row['id'] + '.txt')).write_bytes(row['text'].encode('utf-8'))
        self.check()

    @staticmethod
    def _validated_root(root):
        root = Path(root)
        for parent in [root, *root.parents]:
            if parent.is_symlink() or (hasattr(parent, 'is_junction') and parent.is_junction()):
                raise ValueError('Linked workspace paths are not allowed')
        return root

    def _bind_records(self, records):
        self.search_max_results = 40
        self.records = copy.deepcopy(records)
        identifiers = [row['id'] for row in records]
        if (not records or len(records) > 200 or len(set(identifiers)) != len(records)
                or len({identity.casefold() for identity in identifiers}) != len(records)
                or any(re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', identity) is None for identity in identifiers)
                or any(not isinstance(row.get('text'), str) for row in records)):
            raise ValueError('Invalid input records')
        self.by_id = {row['id']: row for row in self.records}
        self.expected = {row['id']: content_hash(row['text'].encode('utf-8')) for row in self.records}

    @classmethod
    def open(cls, root, records):
        """Open and verify an existing workspace without modifying it."""
        instance = cls.__new__(cls)
        instance.root = cls._validated_root(root)
        if not instance.root.is_dir():
            raise ValueError('Existing workspace is missing')
        instance._bind_records(records)
        instance.check()
        return instance

    @classmethod
    def capture(cls, root, records):
        """Capture an existing workspace, including invalid partial outcomes."""
        instance = cls.__new__(cls)
        instance.root = cls._validated_root(root)
        if not instance.root.is_dir():
            raise ValueError('Existing workspace is missing')
        instance._bind_records(records)
        return instance.audit()

    def audit(self):
        paths = {}
        linked_entries = []
        unexpected_entries = []
        changed_ids = []
        duplicate_ids = []
        for path in self.root.rglob('*'):
            relative = path.relative_to(self.root).as_posix()
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                linked_entries.append(relative)
                continue
            if path.is_dir():
                continue
            if not path.is_file() or path.stat().st_nlink != 1 or path.suffix != '.txt':
                unexpected_entries.append(relative)
                continue
            identity = path.stem
            if identity not in self.expected:
                unexpected_entries.append(relative)
                continue
            if identity in paths:
                duplicate_ids.append(identity)
                continue
            paths[identity] = path
            if content_hash(path.read_bytes()) != self.expected[identity]:
                changed_ids.append(identity)
        missing_ids = sorted(set(self.expected) - set(paths))
        assignments = [
            {'id': row['id'], 'path': list(paths[row['id']].relative_to(self.root).parts[:-1])}
            for row in self.records
            if row['id'] in paths
        ]
        pending = [
            row['id'] for row in assignments
            if not row['path'] or row['path'][0] == 'inbox'
        ]
        valid = not any([
            linked_entries, unexpected_entries, changed_ids, duplicate_ids, missing_ids,
        ])
        return {
            'inventory_preserved': valid,
            'records': len(self.records),
            'captured_records': len(assignments),
            'pending_ids': pending,
            'missing_ids': missing_ids,
            'changed_ids': sorted(set(changed_ids)),
            'duplicate_ids': sorted(set(duplicate_ids)),
            'linked_entries': sorted(linked_entries),
            'unexpected_entries': sorted(unexpected_entries),
            'assignments': assignments,
        }

    def index(self):
        index = {}
        for path in self.root.rglob('*'):
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                raise ValueError('Unexpected linked workspace entry')
            if path.is_dir():
                continue
            if not path.is_file() or path.stat().st_nlink != 1 or path.suffix != '.txt':
                raise ValueError('Unexpected workspace entry')
            identity = path.stem
            if identity not in self.expected or identity in index or content_hash(path.read_bytes()) != self.expected[identity]:
                raise ValueError('Record identity, multiplicity or body changed')
            index[identity] = path
        if index.keys() != self.expected.keys():
            raise ValueError('Missing workspace record')
        return index

    def assignments(self):
        index = self.index()
        return [{'id': row['id'], 'path': list(index[row['id']].relative_to(self.root).parts[:-1])} for row in self.records]

    def check(self):
        assignments = self.assignments()
        pending = [row['id'] for row in assignments if not row['path'] or row['path'][0] == 'inbox']
        return {'inventory_preserved': True, 'records': len(assignments), 'pending_ids': pending, 'assignments': assignments}

    def metadata(self, identity, path):
        row = {key: copy.deepcopy(value) for key, value in self.by_id[identity].items() if key != 'text'}
        row.update(location=path.relative_to(self.root).as_posix(), bytes=path.stat().st_size)
        return row

    def operate(self, name, arguments):
        definitions = {tool['name']: tool for tool in TOOLS}
        if name not in definitions or not isinstance(arguments, dict):
            raise ValueError('Unknown tool or invalid arguments')
        allowed = set(definitions[name]['parameters']['properties'])
        if set(arguments) != allowed:
            raise ValueError('Tool arguments must match its declared schema')
        index = self.index()
        if name == 'check_inventory':
            return self.check()
        if name == 'list_files':
            start = integer(arguments['start_at'], 0, len(self.records))
            count = integer(arguments['max_results'], 1, 200)
            selected = self.records[start:start + count]
            return {'total': len(self.records), 'next_start': start + count if start + count < len(self.records) else None,
                    'files': [self.metadata(row['id'], index[row['id']]) for row in selected]}
        if name == 'read_file':
            identity = arguments['file_id']
            if identity not in index:
                raise ValueError('Unknown file ID')
            offset = integer(arguments['offset'], 0, 10000000)
            length = integer(arguments['length'], 1, 100000)
            text = index[identity].read_bytes().decode('utf-8')
            return {**self.metadata(identity, index[identity]), 'text': text[offset:offset + length],
                    'characters': len(text), 'offset': offset, 'next_offset': offset + length if offset + length < len(text) else None}
        if name == 'search_files':
            query = arguments['query']
            count = integer(arguments['max_results'], 1, self.search_max_results)
            if not isinstance(query, str) or not query.strip() or len(query) > 200:
                raise ValueError('Use a nonempty literal query of at most 200 characters')
            found = []
            for row in self.records:
                position = row['text'].lower().find(query.lower())
                if position >= 0:
                    found.append({'id': row['id'], 'offset': position, 'snippet': row['text'][max(0, position - 120):position + len(query) + 240]})
            return {'matches': found[:count], 'total_matching_records': len(found), 'truncated': len(found) > count}
        identities = arguments['file_ids']
        if (not isinstance(identities, list) or not identities or any(not isinstance(identity, str) for identity in identities)
                or len(set(identities)) != len(identities) or any(identity not in index for identity in identities)):
            raise ValueError('Move IDs must be unique, nonempty and present')
        parts = valid_folder(arguments['folder_path'])
        folder = self.root
        for part in parts:
            if folder.exists() and any(child.name.casefold() == part.casefold() and child.name != part for child in folder.iterdir()):
                raise ValueError('Case-conflicting folder path')
            folder = folder / part
            if folder.is_file():
                raise ValueError('Folder path collides with a file')
        folder.mkdir(parents=True, exist_ok=True)
        moved = []
        try:
            for identity in identities:
                source = index[identity]
                destination = folder / source.name
                if source == destination:
                    continue
                if destination.exists():
                    raise ValueError('Move destination already exists')
                source.rename(destination)
                moved.append((source, destination))
            self.check()
        except Exception:
            for source, destination in reversed(moved):
                destination.rename(source)
            raise
        return {'moved': len(moved), 'file_ids': identities, 'folder_path': parts,
                'unchanged_other_files': len(self.records) - len(identities)}

    def snapshot(self, destination):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for identity, path in self.index().items():
            content = path.read_bytes()
            hashed = content_hash(content)
            blob = destination.parent.parent / 'blobs' / hashed
            blob.parent.mkdir(parents=True, exist_ok=True)
            if blob.exists() and content_hash(blob.read_bytes()) != hashed:
                raise ValueError('Retained workspace blob changed')
            if not blob.exists():
                with blob.open('xb') as stream:
                    stream.write(content)
            rows.append({'id': identity, 'path': path.relative_to(self.root).as_posix(), 'sha256': hashed, 'bytes': len(content)})
        value = {'files': rows, 'public_metadata': [{key: value for key, value in row.items() if key != 'text'} for row in self.records],
                 'scope': 'Exact regular-file paths, UTF-8 bodies and original public metadata. No process, empty-directory or original filesystem-metadata restoration claim.'}
        with destination.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=True, indent=2)
            stream.write('\n')
        return value
