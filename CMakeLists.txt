cmake_minimum_required(VERSION 3.18)

project(AutoPlasm VERSION 0.1.0 LANGUAGES NONE)

set(AUTOPLASM_CONFIG "${CMAKE_SOURCE_DIR}/examples/config_minimal.yaml" CACHE FILEPATH "AutoPlasm config file")
set(AUTOPLASM_ASSEMBLY_CONFIG "${CMAKE_SOURCE_DIR}/examples/config_assembly_full_run.yaml" CACHE FILEPATH "AutoPlasm assembly full-run config file")
set(AUTOPLASM_ILLUMINA_CONFIG "${CMAKE_SOURCE_DIR}/examples/config_illumina_smoke.yaml" CACHE FILEPATH "AutoPlasm Illumina short-read smoke config file")
set(AUTOPLASM_ONT_CONFIG "${CMAKE_SOURCE_DIR}/examples/config_ont_smoke.yaml" CACHE FILEPATH "AutoPlasm ONT long-read smoke config file")
set(AUTOPLASM_HIFI_CONFIG "${CMAKE_SOURCE_DIR}/examples/config_hifi_smoke.yaml" CACHE FILEPATH "AutoPlasm PacBio HiFi smoke config file")
set(AUTOPLASM_HYBRID_CONFIG "${CMAKE_SOURCE_DIR}/examples/config_hybrid_smoke.yaml" CACHE FILEPATH "AutoPlasm hybrid short+long smoke config file")
set(AUTOPLASM_PROFILE "dry_run" CACHE STRING "AutoPlasm profile")

set(_AUTOPLASM_PYTHON_HINTS)
if(DEFINED ENV{CONDA_PREFIX})
  list(APPEND _AUTOPLASM_PYTHON_HINTS "$ENV{CONDA_PREFIX}/bin")
endif()
list(APPEND _AUTOPLASM_PYTHON_HINTS
  "${CMAKE_SOURCE_DIR}/.mamba/envs/autoplasm-base/bin"
  "$ENV{HOME}/miniforge3/bin"
  "$ENV{HOME}/mambaforge/bin"
  "$ENV{HOME}/micromamba/bin"
  "$ENV{HOME}/miniconda3/bin"
)
find_program(DEFAULT_AUTOPLASM_PYTHON NAMES python python3 HINTS ${_AUTOPLASM_PYTHON_HINTS} REQUIRED)
set(AUTOPLASM_PYTHON "${DEFAULT_AUTOPLASM_PYTHON}" CACHE FILEPATH "Python interpreter for AutoPlasm")
find_program(MAMBA_EXE NAMES micromamba mamba HINTS "${CMAKE_SOURCE_DIR}/.mamba/bin")
find_program(CONDA_LOCK_EXE NAMES conda-lock)
set(AUTOPLASM_MAMBA_ROOT "${CMAKE_SOURCE_DIR}/.mamba" CACHE PATH "Repository-local mamba root")

set(AUTOPLASM_ENV
    "${CMAKE_COMMAND}" "-E" "env"
    "PYTHONPATH=${CMAKE_SOURCE_DIR}/src"
)

add_custom_target(configure_autoplasm
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m abi.cli query --type metagenomic_plasmid --what tools
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  COMMENT "Checking AutoPlasm configuration and registry"
)

if(MAMBA_EXE)
  add_custom_target(check_mamba
    COMMAND ${MAMBA_EXE} --version
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    COMMENT "Checking mamba or micromamba"
  )
else()
  add_custom_target(check_mamba
    COMMAND ${CMAKE_COMMAND} -E echo "mamba or micromamba was not found."
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  )
endif()

# The create_envs and lock_envs targets previously referenced stale env
# filenames (base.yml, qc.yml, ...) that no longer exist. Environment
# creation is now driven by scripts/cloud/01_envs.sh, which regenerates
# envs/*.yml from environments.yaml and creates all environments via
# mamba. These targets are kept as deprecation stubs to avoid breaking
# existing automation that calls them.
add_custom_target(create_envs
  COMMAND ${CMAKE_COMMAND} -E echo
          "create_envs is deprecated; use: bash scripts/cloud/01_envs.sh"
  COMMAND ${CMAKE_COMMAND} -E false
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  COMMENT "[DEPRECATED] Use scripts/cloud/01_envs.sh instead"
)

add_custom_target(lock_envs
  COMMAND ${CMAKE_COMMAND} -E echo
          "lock_envs is deprecated; use conda-lock against envs/*.yml directly"
  COMMAND ${CMAKE_COMMAND} -E false
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  COMMENT "[DEPRECATED] Use conda-lock against envs/*.yml directly"
)

add_custom_target(check_tools
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m abi.cli check-resources --type metagenomic_plasmid
          --config ${AUTOPLASM_CONFIG}
          --profile ${AUTOPLASM_PROFILE}
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  COMMENT "Checking registered bioinformatics tools"
)

add_custom_target(check_resources
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m abi.cli check-resources --type metagenomic_plasmid
          --config ${AUTOPLASM_ASSEMBLY_CONFIG}
          --profile local
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  COMMENT "Checking externally prepared databases"
)

add_custom_target(run_assembly_smoke
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m abi.cli run --type metagenomic_plasmid --confirm-execution
          --config ${AUTOPLASM_ASSEMBLY_CONFIG}
          --profile local
          --outdir ${CMAKE_SOURCE_DIR}/results/assembly_full_run
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  COMMENT "Running AutoPlasm assembly-only full smoke workflow"
)

add_custom_target(run_illumina_smoke_dry
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m abi.cli dry-run --type metagenomic_plasmid --no-check-files --no-progress
          --config ${AUTOPLASM_ILLUMINA_CONFIG}
          --profile dry_run
          --outdir ${CMAKE_SOURCE_DIR}/results/illumina_smoke_dry
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  COMMENT "Running AutoPlasm Illumina short-read smoke dry-run workflow"
)

add_custom_target(run_ont_smoke_dry
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m abi.cli dry-run --type metagenomic_plasmid --no-check-files --no-progress
          --config ${AUTOPLASM_ONT_CONFIG}
          --profile dry_run
          --outdir ${CMAKE_SOURCE_DIR}/results/ont_smoke_dry
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  COMMENT "Running AutoPlasm ONT long-read smoke dry-run workflow"
)

add_custom_target(run_hifi_smoke_dry
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m abi.cli dry-run --type metagenomic_plasmid --no-check-files --no-progress
          --config ${AUTOPLASM_HIFI_CONFIG}
          --profile dry_run
          --outdir ${CMAKE_SOURCE_DIR}/results/hifi_smoke_dry
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  COMMENT "Running AutoPlasm PacBio HiFi smoke dry-run workflow"
)

add_custom_target(run_hybrid_smoke_dry
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m abi.cli dry-run --type metagenomic_plasmid --no-check-files --no-progress
          --config ${AUTOPLASM_HYBRID_CONFIG}
          --profile dry_run
          --outdir ${CMAKE_SOURCE_DIR}/results/hybrid_smoke_dry
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  COMMENT "Running AutoPlasm hybrid short+long smoke dry-run workflow"
)

enable_testing()
add_test(
  NAME pytest
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m pytest ${CMAKE_SOURCE_DIR}/tests
)
add_test(
  NAME autoplasm_help
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m abi.cli --help
)
add_test(
  NAME ruff
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m ruff check
          ${CMAKE_SOURCE_DIR}/src ${CMAKE_SOURCE_DIR}/tests
)
add_test(
  NAME ruff_format_src
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m ruff format --check
          ${CMAKE_SOURCE_DIR}/src
)
add_test(
  NAME ruff_format_tests
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m ruff format --check
          ${CMAKE_SOURCE_DIR}/tests
)
add_test(
  NAME mypy
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m mypy
          ${CMAKE_SOURCE_DIR}/src
)
add_test(
  NAME autoplasm_dry_run
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m abi.cli dry-run --type metagenomic_plasmid --no-check-files --no-progress
          --config ${CMAKE_SOURCE_DIR}/examples/config_minimal.yaml
          --profile dry_run
          --outdir ${CMAKE_BINARY_DIR}/autoplasm_dry_run
)
add_test(
  NAME autoplasm_illumina_dry_run
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m abi.cli dry-run --type metagenomic_plasmid --no-check-files --no-progress
          --config ${AUTOPLASM_ILLUMINA_CONFIG}
          --profile dry_run
          --outdir ${CMAKE_BINARY_DIR}/autoplasm_illumina_dry_run
)
add_test(
  NAME autoplasm_ont_dry_run
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m abi.cli dry-run --type metagenomic_plasmid --no-check-files --no-progress
          --config ${AUTOPLASM_ONT_CONFIG}
          --profile dry_run
          --outdir ${CMAKE_BINARY_DIR}/autoplasm_ont_dry_run
)
add_test(
  NAME autoplasm_hifi_dry_run
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m abi.cli dry-run --type metagenomic_plasmid --no-check-files --no-progress
          --config ${AUTOPLASM_HIFI_CONFIG}
          --profile dry_run
          --outdir ${CMAKE_BINARY_DIR}/autoplasm_hifi_dry_run
)
add_test(
  NAME autoplasm_hybrid_dry_run
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m abi.cli dry-run --type metagenomic_plasmid --no-check-files --no-progress
          --config ${AUTOPLASM_HYBRID_CONFIG}
          --profile dry_run
          --outdir ${CMAKE_BINARY_DIR}/autoplasm_hybrid_dry_run
)
set_tests_properties(
  pytest
  autoplasm_help
  ruff
  ruff_format_src
  ruff_format_tests
  mypy
  autoplasm_dry_run
  autoplasm_illumina_dry_run
  autoplasm_ont_dry_run
  autoplasm_hifi_dry_run
  autoplasm_hybrid_dry_run
  PROPERTIES
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  TIMEOUT 120
)

add_custom_target(run_tests
  COMMAND ${CMAKE_CTEST_COMMAND} --output-on-failure
  WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
  COMMENT "Running AutoPlasm tests through CTest"
)

add_custom_target(run_pipeline
  COMMAND ${AUTOPLASM_ENV} ${AUTOPLASM_PYTHON} -m abi.cli dry-run --type metagenomic_plasmid --no-check-files --no-progress
          --config ${AUTOPLASM_CONFIG}
          --profile ${AUTOPLASM_PROFILE}
          --outdir ${CMAKE_SOURCE_DIR}/results/autoplasm_project
  WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
  COMMENT "Running AutoPlasm dry-run pipeline"
)
