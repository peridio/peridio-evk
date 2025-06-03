from peridio_evk.utils import *
from peridio_evk.log import *

def do_create_artifacts(organization_prn, cohort_prn):
    log_task('Creating Artifacts')
    artifacts_start = [
        {'name': 'edge-inference-os', 'description': 'Edge Inference Product OS', 'version': 'v1.12.1', 'targets': [{'target': 'arm64-v8', 'bytes': 67108864}, {'target': 'x86_64', 'bytes': 69206016}],
            "custom_metadata": {"peridiod": {"installer": "fwup", "installer_opts": {"cache_enabled": False}, "reboot_required": True}}},
        {'name': 'edge-inference-service', 'description': 'Edge Inference Service', 'version': 'v1.5.3', 'targets': [{'target': 'arm64-v8', 'bytes': 10485760}, {'target': 'x86_64', 'bytes': 14680064}],
            "custom_metadata": {"peridiod": {"installer": "file", "installer_opts": {"path": "/opt/edge-inference", "name": "edge-inference-service.img", "reboot_required": False}}}},
        {'name': 'edge-inference-peripheral', 'description': 'Edge Inference Peripheral Firmware', 'version': 'v1.9.10', 'targets': [{'target': 'arm-cortex-m33', 'bytes': 2097152}],
            "custom_metadata": {"peridiod": {"installer": "file", "installer_opts": {"path": "/opt/edge-inference", "name": "edge-inference-peripheral.bin", "reboot_required": False}}}},
        {'name': 'edge-inference-model', 'description': 'Edge Inference ML Model', 'version': 'v1.4.0', 'targets': [{'target': 'arm-ethos-u65', 'bytes': 33554432}],
            "custom_metadata": {"peridiod": {"installer": "file", "installer_opts": {"path": "/opt/edge-inference", "name": "edge-inference-model.onnx", "reboot_required": False}}}}
    ]

    artifacts_end = [
        {'name': 'edge-inference-os', 'description': 'Edge Inference Product OS', 'version': 'v1.12.1', 'targets': [{'target': 'arm64-v8', 'bytes': 67108864}, {'target': 'x86_64', 'bytes': 69206016}],
            "custom_metadata": {"peridiod": {"installer": "fwup", "installer_opts": {"cache_enabled": False}, "reboot_required": True}}},
        {'name': 'edge-inference-service', 'description': 'Edge Inference Service', 'version': 'v2.0.0', 'targets': [{'target': 'arm64-v8', 'bytes': 10486260}, {'target': 'x86_64', 'bytes': 14685064}],
            "custom_metadata": {"peridiod": {"installer": "file", "installer_opts": {"path": "/opt/edge-inference", "name": "edge-inference-service.img", "reboot_required": False}}}},
        {'name': 'edge-inference-peripheral', 'description': 'Edge Inference Peripheral Firmware', 'version': 'v1.9.10', 'targets': [{'target': 'arm-cortex-m33', 'bytes': 2097152}],
            "custom_metadata": {"peridiod": {"installer": "file", "installer_opts": {"path": "/opt/edge-inference", "name": "edge-inference-peripheral.bin", "reboot_required": False}}}},
        {'name': 'edge-inference-model', 'description': 'Edge Inference ML Model', 'version': 'v2.1.0', 'targets': [{'target': 'arm-ethos-u65', 'bytes': 43554432}],
            "custom_metadata": {"peridiod": {"installer": "file", "installer_opts": {"path": "/opt/edge-inference", "name": "edge-inference-model.onnx", "reboot_required": False}}}}
    ]

    bundle_start, artifacts = do_create_artifacts_bundle(artifacts_start, 'r1001', organization_prn)
    bundle_end, _artifacts = do_create_artifacts_bundle(artifacts_end, 'r1002', organization_prn)

    release_from = do_create_release('release-r1001', organization_prn, cohort_prn, bundle_start, '1.1.0', '', False, [])
    do_create_release('release-r1002', organization_prn, cohort_prn, bundle_end, '2.0.0', '~> 1.1', True, ['canary'])
    return release_from, artifacts

def do_create_artifacts_bundle(artifacts, bundle_name, organization_prn):
    for artifact in artifacts:
        log_info(f'{artifact["name"]}: {artifact["version"]}')
    artifact_version_prns = []
    for artifact in artifacts:
        evk_config = read_evk_config()
        result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'artifacts', 'create', '--organization-prn', evk_config['organization_prn'], '--name', artifact['name'], '--description', artifact['description'], '--custom-metadata', json.dumps(artifact['custom_metadata'])])
        if result.returncode != 0:
            log_skip_task('Artifact Exists')
            result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'artifacts', 'list', '--search', f'name:\'{artifact["name"]}\''])
            response = json.loads(result.stdout)
            artifact_prn = response['artifacts'][0]['prn']
        else:
            log_task('Creating Artifact')
            response = json.loads(result.stdout)
            artifact_prn = response['artifact']['prn']
            log_info(f'Artifact PRN: {artifact_prn}')

        result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'artifact-versions', 'create', '--artifact-prn', artifact_prn, '--version', artifact['version'], '--description', artifact['version']])
        if result.returncode != 0:
            log_skip_task('Artifact Version Exists')
            result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'artifact-versions', 'list', '--search', f'artifact_prn:\'{artifact_prn}\' and description:\'{artifact["version"]}\''])
            response = json.loads(result.stdout)
            artifact_version_prn = response['artifact_versions'][0]['prn']
        else:
            log_task('Creating Artifact Version')
            response = json.loads(result.stdout)
            artifact_version_prn = response['artifact_version']['prn']
            log_info(f'Artifact Version PRN: {artifact_version_prn}')

        artifact_version_prns.append(artifact_version_prn)

        config_path = get_config_path()
        artifacts_path = os.path.join(config_path, 'evk-data', 'artifacts')
        if not os.path.exists(artifacts_path):
            os.makedirs(artifacts_path)

        for target in artifact['targets']:
            artifact_binary_path = os.path.join(artifacts_path, f'{artifact["name"]}-{artifact["version"]}-{target["target"]}')
            if not os.path.exists(artifact_binary_path):
                log_task('Creating Artifact Binary')
                generate_random_bytes_file(artifact_binary_path, target['bytes'])
                log_modify_file(artifact_binary_path)
            else:
                log_skip_task('Artifact Binary Exists')

            result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'binaries', 'create', '--artifact-version-prn', artifact_version_prn, '--target', target['target'], '--content-path', artifact_binary_path, '--signing-key-pair', 'release-signing-key'])
            if result.returncode != 0:
                response = json.loads(result.stdout)
                binary_prn = response['binaries'][0]['prn']
                log_info(f'Binary PRN: {binary_prn}')
            else:
                response = json.loads(result.stdout)
                binary_prn = response['binary']['prn']
                log_info(f'Binary PRN: {binary_prn}')
            target['binary_prn'] = binary_prn

    result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'bundles', 'create', '--artifact-version-prns', f'{",".join(artifact_version_prns)}', '--name', bundle_name, '--organization-prn', organization_prn])
    if result.returncode == 0:
        log_task('Creating Bundle')
        log_info(f'Bundle Name: {bundle_name}')
        response = json.loads(result.stdout)
        bundle_prn = response['bundle']['prn']
    else:
        log_skip_task('Bundle already Exists')
        result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'bundles', 'list', '--search', f'name:\'{bundle_name}\''])
        response = json.loads(result.stdout)
        bundle_prn = response['bundles'][0]['prn']
    return bundle_prn, artifacts

def do_create_release(release_name, organization_prn, cohort_prn, bundle_prn, version, version_requirement, disabled, phase_tags):
    log_task('Create Release')
    log_info(f'Release Name: {release_name}')
    log_info(f'Cohort PRN: {cohort_prn}')
    log_info(f'Bundle PRN: {bundle_prn}')

    evk_config = read_evk_config()
    current_time = get_current_time_iso8601()

    command = ['peridio', '--profile', evk_config['profile'], 'releases', 'create', '--organization-prn', organization_prn, '--bundle-prn', bundle_prn, '--cohort-prn', cohort_prn, '--name', release_name, '--schedule-date', current_time, '--disabled', boolean_to_string_lower(disabled), '--version', version, '--version-requirement', version_requirement]

    if not phase_tags:
        command.append('--phase-value')
        command.append('1.0')
    else:
        command.append('--phase-tags')
        command.append(f'{",".join(phase_tags)}')

    result = peridio_cli(command)
    if result.returncode == 0:
        response = json.loads(result.stdout)
        release = response['release']
    else:
        result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'releases', 'list', '--search', f'version:\'{version}\''])
        if result.returncode == 0:
            response = json.loads(result.stdout)
            release = response['releases'][0]
    return release
