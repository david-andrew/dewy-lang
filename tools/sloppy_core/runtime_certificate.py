"""Chain unchanged runtime artifacts to accepted per-workload comparisons.

This supplies code-equivalence evidence, never samples or fresh C speed ratios.
Compiler latency is still measured; every runtime binary still gets boundary
checks and a full-size checksum run. Missing evidence falls back to timing.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.sloppy_core.benchmark_apps import (
    equivalent_artifact,
    equivalent_canonical_artifact,
)


class RuntimeCertificate:
    def __init__(self, path: Path, identities: dict):
        contents = path.read_bytes()
        document = json.loads(contents)
        stage = document.get('stage_measurement', document.get('initial_stage_measurement', document))
        assessment = document.get('final_assessment', stage.get('assessment', {}))
        comparisons = assessment.get('comparisons', {})
        # Compilation uncertainty or an unrelated kernel does not invalidate
        # an independently passing runtime comparison. prove() still requires
        # acceptance against the fixed reference for both modes of this kernel.
        if stage.get('status') != 'complete' or not comparisons:
            raise ValueError('The previous runtime report must be complete and assessed')
        previous = identities.get('previous')
        if previous is None or stage.get('toolchains', {}).get('candidate') != previous:
            raise ValueError('The previous report does not identify the supplied previous toolchain')
        if stage.get('toolchains', {}).get('reference') != identities['reference']:
            raise ValueError('The previous report does not use the same fixed reference toolchain')
        self.runtime = stage.get('runtime', {})
        self.comparisons = comparisons
        self.report_sha256 = hashlib.sha256(contents).hexdigest()

    def prove(self, name: str, current: dict, workload: dict) -> dict | None:
        old = self.runtime.get('workloads', {}).get(name)
        if not old or current.get('target') != 'native' or current.get('mode') != 'both':
            return None
        for key in ('target', 'mode', 'core_flags', 'kernel_clock', 'harness_sha256',
                    'c_harness_sha256', 'measured_harness_sha256'):
            if key not in current or self.runtime.get(key) != current[key]:
                return None
        for key in ('count', 'source_sha256', 'adapted_source_sha256', 'c_source_sha256'):
            if key not in workload or old.get(key) != workload[key]:
                return None
        artifacts = workload.get('artifact_identity', {})
        canonical = {}
        for mode in ('default', 'release'):
            accepted = self.comparisons.get(f'runtime/{name}/{mode}/reference', {})
            if accepted.get('status') != 'pass':
                return None
            old_variant = self.runtime.get('variants', {}).get(f'candidate-{mode}', {})
            for label in ('previous', 'candidate'):
                variant = current.get('variants', {}).get(f'{label}-{mode}', {})
                if 'flags' not in old_variant or old_variant['flags'] != variant.get('flags'):
                    return None
            previous = artifacts.get(f'previous-{mode}', {})
            candidate = artifacts.get(f'candidate-{mode}', {})
            accepted_artifact = old.get('artifact_identity', {}).get(f'candidate-{mode}', {})
            if not equivalent_artifact(previous, candidate):
                return None
            if not equivalent_canonical_artifact(previous, accepted_artifact):
                return None
            canonical[mode] = previous['canonical_sha256']
        return {'evidence': 'candidate matches the previous artifact; that artifact matches accepted runtime comparisons '
                            'after masking equal-width bundle/input paths, with identical workload and harness sources',
                'previous_report_sha256': self.report_sha256,
                'accepted_artifact_canonical_sha256': canonical}
