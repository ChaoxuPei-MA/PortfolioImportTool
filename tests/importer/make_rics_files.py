"""
Synthetic RICS bulk-import tree generator for integration tests.

Writes a minimal but valid directory tree that read_rics_files / process_GCP_imports
and process_portfolio_imports can consume end-to-end without a live SG.

Tree produced under `target_dir/`:
  granularCounterparty/
    GC/
      1_GCP.csv
      2_IndustryFactorLoadingsParameterSet.csv
      3_GCP_ChildModelTypes.csv
      4_GCP_ChildBond.csv
  portfolio/
    CompositePortfolio.csv
    CompositePortfolio_HoldingsParameterSet.csv

Column sets confirmed against:
  - pit/importer/read_rics_files.py  (read_rics_files)
  - pit/importer/pipeline.py         (import_GCP_nonagency_mbs, process_portfolio_imports,
                                       import_param_set_by_name, import_param_set)
"""
import os


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as fh:
        fh.write(content)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def make_minimal_rics_tree(target_dir: str) -> None:
    """
    Write a minimal but valid RICS bulk-import file tree into *target_dir*.

    File layout
    -----------
    <target_dir>/
      granularCounterparty/
        GC/
          1_GCP.csv                          -- GranularCounterparty issuer master
          2_IndustryFactorLoadingsParameterSet.csv
          3_GCP_ChildModelTypes.csv          -- declares "Bond" child type
          4_GCP_ChildBond.csv                -- one bond per issuer
      portfolio/
        CompositePortfolio.csv
        CompositePortfolio_HoldingsParameterSet.csv
    """

    gc_dir = os.path.join(target_dir, "granularCounterparty", "GC")
    pf_dir = os.path.join(target_dir, "portfolio")

    # ------------------------------------------------------------------
    # 1_GCP.csv
    # Columns required by import_GCP_nonagency_mbs:
    #   Name            -- issuer identifier (used in FindModelByName after import)
    #   TransitionMatrix-- collected into model_lists['transition_matrices']
    #   MPRModel        -- matched by "MPR" substring -> model_lists['mpr_models']
    #   Z-ScoreModel    -- matched by "ScoreModel" substring -> model_lists['zscore_models']
    #   Economy         -- (optional but expected by BulkImporter schema)
    # ------------------------------------------------------------------
    _write(
        os.path.join(gc_dir, "1_GCP.csv"),
        "Name,TransitionMatrix,MPRModel,Z-ScoreModel,Economy\n"
        "ISSUER1,Base,Base,Base,CAD\n"
        "ISSUER2,Base,Base,Base,CAD\n",
    )

    # ------------------------------------------------------------------
    # 2_IndustryFactorLoadingsParameterSet.csv
    # import_param_set_by_name('IndustryFactorLoadings', ...) is called for
    # model_type == "" (GC subfolder). import_param_set reads the file as a
    # DataFrame and sorts by the first three columns; the columns just need to
    # exist. It then calls ParameterSetImporter.Import(issuers, nameChild, data, depth).
    # The file is matched by "IndustryFactorLoadings" being a substring of the path.
    # ------------------------------------------------------------------
    _write(
        os.path.join(gc_dir, "2_IndustryFactorLoadingsParameterSet.csv"),
        "Name,Factor,Value\n"
        "ISSUER1,Industry1,0.5\n"
        "ISSUER2,Industry1,0.5\n",
    )

    # ------------------------------------------------------------------
    # 3_GCP_ChildModelTypes.csv
    # import_GCP_nonagency_mbs reads this file to discover child types.
    # Columns: Name (bond full ID used as output_data), Type (child model type).
    # The child file lookup pattern is: Child{Type}.csv  (or Child{Type}{model_type}.csv)
    # ------------------------------------------------------------------
    _write(
        os.path.join(gc_dir, "3_GCP_ChildModelTypes.csv"),
        "Name,Type\n"
        "ISSUER1.Bond1,Bond\n"
        "ISSUER2.Bond2,Bond\n",
    )

    # ------------------------------------------------------------------
    # 4_GCP_ChildBond.csv
    # Matched by: re.search(rf"Child{child_type}\.csv$", basename)
    # i.e. "ChildBond.csv" in the filename.
    # Columns: Name (full dotted ID e.g. "ISSUER1.Bond1"), Economy (optional).
    # parent_name is extracted as the part before the first ".".
    # create_child_model is called: parent_issuer.AddModel("Bond"), new_model.Name = bond_id
    # ------------------------------------------------------------------
    _write(
        os.path.join(gc_dir, "4_GCP_ChildBond.csv"),
        "Name,Economy\n"
        "ISSUER1.Bond1,CAD\n"
        "ISSUER2.Bond2,CAD\n",
    )

    # ------------------------------------------------------------------
    # portfolio/CompositePortfolio.csv
    # process_portfolio_imports reads this and sorts by first column.
    # Columns: Name (portfolio name), Economy, WeightDefinition.
    # ------------------------------------------------------------------
    _write(
        os.path.join(pf_dir, "CompositePortfolio.csv"),
        "Name,Economy,WeightDefinition\n"
        "TestPortfolio,CAD,EqualWeight\n",
    )

    # ------------------------------------------------------------------
    # portfolio/CompositePortfolio_HoldingsParameterSet.csv
    # Matched by "HoldingsParameterSet" substring in file name.
    # import_param_set reads it; needs >= 3 columns to sort by first three.
    # Columns: Name, ParameterSetIndex, Asset, Weight, CurrencyHedge.
    # ------------------------------------------------------------------
    _write(
        os.path.join(pf_dir, "CompositePortfolio_HoldingsParameterSet.csv"),
        "Name,ParameterSetIndex,Asset,Weight,CurrencyHedge\n"
        "TestPortfolio,1,ISSUER1.Bond1,1.0,None\n",
    )
