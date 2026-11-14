# Becher test suite: reliability and utility scorecard

Applies to **all 160 collected pytest cases** in this reviewed build. Parameterized cases are individually listed in `TEST_SCORES.csv`; the table below groups cases sharing the same test function and score. No test receives credit for human visual validation.

**Rubric:** reliability 1–5 = likelihood of detecting a real violation without false passes or ordering dependence; utility 1–5 = value for preserving the accepted renderer, geometry, data and workflows during agent refactoring. Five is strongest. These are review judgements, not measured probabilities. High ratings beyond golden outputs have not all been mutation-tested.

| Reliability | Cases |
|---:|---:|
| 1 | 0 |
| 2 | 0 |
| 3 | 0 |
| 4 | 114 |
| 5 | 46 |

## Every surviving test definition

| Test (parameterized count) | Reliability | Utility | Rationale |
|---|---:|---:|---|
| `tests/test_architectural_generation.py::ArchitectureTests::test_active_data_grammars_and_valid_assembly` (1) | 4 | 3 | Current catalogue/content contract; meaningful but can require deliberate updates as designs change |
| `tests/test_architectural_generation.py::ArchitectureTests::test_invalid_detached_annex_is_rejected` (1) | 4 | 4 | Negative-path or tampering test; checks a failure mode beyond successful execution |
| `tests/test_architectural_generation.py::ArchitectureTests::test_invalid_roof_and_unsupported_feature_rejected` (1) | 4 | 4 | Negative-path or tampering test; checks a failure mode beyond successful execution |
| `tests/test_architectural_generation.py::ArchitectureTests::test_mesh_rotations_and_indexed_light` (1) | 4 | 4 | Active geometry and candidate-policy checks; some assertions depend on selected seed or grammar |
| `tests/test_architectural_generation.py::ArchitectureTests::test_mutations_do_not_rewrite_nonroof_components` (1) | 4 | 4 | Active geometry and candidate-policy checks; some assertions depend on selected seed or grammar |
| `tests/test_architectural_generation.py::ArchitectureTests::test_reroll_only_roof_not_building_dimensions` (1) | 4 | 4 | Active geometry and candidate-policy checks; some assertions depend on selected seed or grammar |
| `tests/test_architectural_generation.py::ArchitectureTests::test_structural_mutation_is_seeded` (1) | 4 | 4 | Active geometry and candidate-policy checks; some assertions depend on selected seed or grammar |
| `tests/test_facade_decals.py::test_decals_are_flush_keep_depth_and_non_facade_hits` (4) | 4 | 3 | Current facade / decoration contract; deterministic and mostly positive assertions |
| `tests/test_facade_decals.py::test_old_box_mode_retains_default_bytes` (1) | 4 | 3 | Current facade / decoration contract; deterministic and mostly positive assertions |
| `tests/test_golden_outputs.py::test_approved_sprites_geometry_and_scene` (3) | 5 | 5 | Frozen independent pixel/palette and scene/mesh oracles; detects deliberate render and geometry mutations |
| `tests/test_high_sun_direction.py::test_high_sun_top_brighter_than_visible_walls` (4) | 5 | 5 | Precise fixed-light/camera invariant; directly protects a previously observed lighting defect |
| `tests/test_high_sun_direction.py::test_screen_relative_brightness_stable_across_rotations` (4) | 5 | 5 | Precise fixed-light/camera invariant; directly protects a previously observed lighting defect |
| `tests/test_high_sun_direction.py::test_sun_is_significantly_elevated` (1) | 5 | 5 | Precise fixed-light/camera invariant; directly protects a previously observed lighting defect |
| `tests/test_mesh_architecture.py::test_box_outward_normals` (1) | 5 | 5 | Geometry or coordinate-space invariant with an explicit discriminating mathematical assertion |
| `tests/test_mesh_architecture.py::test_camera_rotation_does_not_modify_baked_world_normals` (1) | 5 | 5 | Precise fixed-light/camera invariant; directly protects a previously observed lighting defect |
| `tests/test_mesh_architecture.py::test_cylinder_side_normals_and_caps` (1) | 4 | 5 | Core mesh/renderer integration, roundtrip, and frozen geometry contract |
| `tests/test_mesh_architecture.py::test_factory_render_contract` (24) | 4 | 5 | Core mesh/renderer integration, roundtrip, and frozen geometry contract |
| `tests/test_mesh_architecture.py::test_generic_occlusion_not_scene_order` (1) | 5 | 5 | Geometry or coordinate-space invariant with an explicit discriminating mathematical assertion |
| `tests/test_mesh_architecture.py::test_mesh_bake_roundtrip` (1) | 4 | 5 | Core mesh/renderer integration, roundtrip, and frozen geometry contract |
| `tests/test_mesh_architecture.py::test_pipeline_freezes_once_and_prevents_backend_cache_collision` (1) | 4 | 5 | Core mesh/renderer integration, roundtrip, and frozen geometry contract |
| `tests/test_mesh_camera_light.py::test_camera_and_light_use_same_coordinate_convention` (4) | 4 | 4 | Deterministic pixel-treatment or lighting constraints; mostly isolated tests |
| `tests/test_mesh_camera_light.py::test_light_dot_product_coordinate_equivalence` (4) | 5 | 5 | Geometry or coordinate-space invariant with an explicit discriminating mathematical assertion |
| `tests/test_mesh_camera_light.py::test_light_rotation_known_quarter_turns` (4) | 5 | 5 | Precise fixed-light/camera invariant; directly protects a previously observed lighting defect |
| `tests/test_mesh_camera_light.py::test_world_geometry_unchanged_by_light_turn` (4) | 5 | 5 | Precise fixed-light/camera invariant; directly protects a previously observed lighting defect |
| `tests/test_modular_grammar_trial.py::test_broad_lower_masses_and_roof_variety` (1) | 4 | 4 | Active geometry and candidate-policy checks; some assertions depend on selected seed or grammar |
| `tests/test_modular_grammar_trial.py::test_stable_exact_edge_span_and_valid_features` (1) | 4 | 4 | Active geometry and candidate-policy checks; some assertions depend on selected seed or grammar |
| `tests/test_roof_colour.py::test_main_monitor_roof_inherits_primary_hue` (1) | 4 | 4 | Deterministic pixel-treatment or lighting constraints; mostly isolated tests |
| `tests/test_roof_colour.py::test_roof_colour_only_changes_secondary_roof_pixels` (1) | 4 | 4 | Deterministic pixel-treatment or lighting constraints; mostly isolated tests |
| `tests/test_semantic_colour.py::SemanticColourTests::test_default_on_and_disabling_matches_original_shaded_pixels` (1) | 4 | 4 | Deterministic pixel-treatment or lighting constraints; mostly isolated tests |
| `tests/test_semantic_colour.py::SemanticColourTests::test_hues_are_bounded_and_stable` (1) | 4 | 4 | Deterministic pixel-treatment or lighting constraints; mostly isolated tests |
| `tests/test_semantic_colour.py::SemanticColourTests::test_material_category_ranges_are_respected` (1) | 4 | 4 | Deterministic pixel-treatment or lighting constraints; mostly isolated tests |
| `tests/test_step3_pipeline.py::FeatureTests::test_fabric_is_untouched` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step3_pipeline.py::FeatureTests::test_four_independent_passes` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step3_pipeline.py::FeatureTests::test_invalid_detached_feature_rejected` (1) | 4 | 4 | Negative-path or tampering test; checks a failure mode beyond successful execution |
| `tests/test_step3_pipeline.py::FeatureTests::test_locked_reroll_is_rejected` (1) | 4 | 4 | Negative-path or tampering test; checks a failure mode beyond successful execution |
| `tests/test_step3_pipeline.py::FeatureTests::test_mesh_render_and_palette` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step3_pipeline.py::FeatureTests::test_seeded_repeatability` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step3_pipeline.py::PipelineTests::test_deterministic_reroll` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step3_pipeline.py::PipelineTests::test_four_real_rotations_and_npz` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step3_pipeline.py::PipelineTests::test_not_valid_candidate_key` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step3_pipeline.py::PipelineTests::test_persistent_lineage_and_select` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step3_pipeline.py::PipelineTests::test_rebuild_is_idempotent_preserves_feedback` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step3_pipeline.py::PipelineTests::test_reviews_locks_and_rejections` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step4_handoff.py::Step4HandoffTests::test_candidate_append_preserves_existing_artwork` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step4_handoff.py::Step4HandoffTests::test_colour_branches_do_not_change_silhouette` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step4_handoff.py::Step4HandoffTests::test_different_lighting_changes_shading_not_geometry` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step4_handoff.py::Step4HandoffTests::test_four_views_and_valid_palette` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step4_handoff.py::Step4HandoffTests::test_grade_cannot_ray_cast_and_is_repeatable` (1) | 4 | 4 | Negative-path or tampering test; checks a failure mode beyond successful execution |
| `tests/test_step4_handoff.py::Step4HandoffTests::test_hand_off_re_run_is_idempotent` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step4_handoff.py::Step4HandoffTests::test_importing_outside_geometry_is_rejected` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step4_handoff.py::Step4HandoffTests::test_rgba_artist_overlay_import` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step4_handoff.py::Step4HandoffTests::test_seed_reference_scene_not_modified` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step4_handoff.py::Step4HandoffTests::test_semantic_masks_partition_all_pixels` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step5_selection.py::SelectionTests::test_01_assess_repeatable_non_destructive` (1) | 4 | 4 | Isolated fixture copies with explicit voted/refilled preconditions; runnable individually |
| `tests/test_step5_selection.py::SelectionTests::test_02_vote_preflight` (1) | 4 | 4 | Isolated fixture copies with explicit voted/refilled preconditions; runnable individually |
| `tests/test_step5_selection.py::SelectionTests::test_03_vote_refill_retain_art_and_repeatability` (1) | 4 | 4 | Isolated fixture copies with explicit voted/refilled preconditions; runnable individually |
| `tests/test_step5_selection.py::SelectionTests::test_04_export_accepted_and_native_palette` (1) | 4 | 4 | Isolated fixture copies with explicit voted/refilled preconditions; runnable individually |
| `tests/test_step5_selection.py::SelectionTests::test_05_archived_missing_from_active_evaluation_and_export` (1) | 4 | 4 | Isolated fixture copies with explicit voted/refilled preconditions; runnable individually |
| `tests/test_step5_selection.py::SelectionTests::test_06_palette_mismatch_is_hard_failure` (1) | 4 | 4 | Isolated fixture copies with explicit voted/refilled preconditions; runnable individually |
| `tests/test_step5_selection.py::SelectionTests::test_07_approved_only_cli_handoff` (1) | 4 | 4 | Isolated fixture copies with explicit voted/refilled preconditions; runnable individually |
| `tests/test_step7_sawtooth.py::SawtoothRayTests::test_clerestory_pixels_are_exposed_by_depth_test` (1) | 4 | 4 | Current sawtooth geometry visibility; seed-specific reference and pixel thresholds |
| `tests/test_step7_sawtooth.py::SawtoothRayTests::test_sawtooth_render_is_deterministic` (1) | 4 | 4 | Current sawtooth geometry visibility; seed-specific reference and pixel thresholds |
| `tests/test_step7_sawtooth.py::SawtoothRayTests::test_thin_sheets_have_correct_plane_normal` (1) | 5 | 5 | Geometry or coordinate-space invariant with an explicit discriminating mathematical assertion |
| `tests/test_step8_edge_contrast.py::EdgeContrastTests::test_all_families_all_rotations_preserve_exact_geometry` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step8_edge_contrast.py::EdgeContrastTests::test_cli_edges_from_geometry_writes_indexed_files` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step8_edge_contrast.py::EdgeContrastTests::test_glass_details_foundations_untouched` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step8_edge_contrast.py::EdgeContrastTests::test_rejects_repainting_geometry_silhouette` (1) | 4 | 4 | Negative-path or tampering test; checks a failure mode beyond successful execution |
| `tests/test_step8_edge_contrast.py::EdgeContrastTests::test_repeatable_and_idempotent` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step8_edge_contrast.py::EdgeContrastTests::test_saved_surface_roles_roundtrip` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_step8_edge_contrast.py::PipelineEdgeIntegrationTests::test_pipeline_on_off_have_identical_saved_base_and_distinct_pngs` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_v0111_integrity.py::test_cache_validates_absent_and_modified_sprites` (1) | 4 | 4 | Negative-path or tampering test; checks a failure mode beyond successful execution |
| `tests/test_v0111_integrity.py::test_refill_matches_selected_render_options_all_four_rotations` (1) | 4 | 4 | Behavioural integration or export contract; meaningful but may have moderate cost and redundant setup |
| `tests/test_v0121_facade_clearance.py::test_decal_does_not_modify_depth_normals_or_scene_silhouette` (1) | 4 | 3 | Current facade / decoration contract; deterministic and mostly positive assertions |
| `tests/test_v0121_facade_clearance.py::test_door_clearance_across_profiles_and_all_bof_fabric` (1) | 4 | 3 | Current facade / decoration contract; deterministic and mostly positive assertions |
| `tests/test_v012_industrial_facades.py::test_bof_family_profiles_are_declared_and_valid` (1) | 4 | 3 | Current catalogue/content contract; meaningful but can require deliberate updates as designs change |
| `tests/test_v012_industrial_facades.py::test_unknown_profile_rejected_at_grammar_load` (1) | 4 | 4 | Negative-path or tampering test; checks a failure mode beyond successful execution |
| `tests/test_v012_industrial_facades.py::test_windows_and_doors_are_only_grammar_assigned_decal_panels` (1) | 4 | 3 | Current facade / decoration contract; deterministic and mostly positive assertions |
| `tests/test_v014_catalogue.py::test_approved_family_mass_properties_and_validity` (1) | 4 | 4 | Active geometry and candidate-policy checks; some assertions depend on selected seed or grammar |
| `tests/test_v014_catalogue.py::test_four_view_native_sprites_all_families` (1) | 4 | 4 | Active geometry and candidate-policy checks; some assertions depend on selected seed or grammar |
| `tests/test_v014_catalogue.py::test_six_approved_default_families` (1) | 4 | 3 | Current catalogue/content contract; meaningful but can require deliberate updates as designs change |
| `tests/test_v015_sampling.py::test_current_catalogues_and_defaults` (1) | 4 | 4 | Active geometry and candidate-policy checks; some assertions depend on selected seed or grammar |
| `tests/test_v015_sampling.py::test_diverse_is_reproducible_and_stronger_than_first_twelve` (1) | 4 | 4 | Active geometry and candidate-policy checks; some assertions depend on selected seed or grammar |
| `tests/test_v015_sampling.py::test_pipeline_refill_retains_related_policy` (1) | 4 | 4 | Active geometry and candidate-policy checks; some assertions depend on selected seed or grammar |
| `tests/test_v015_sampling.py::test_primary_edge_span_and_ancillary_are_contained` (1) | 4 | 4 | Active geometry and candidate-policy checks; some assertions depend on selected seed or grammar |
| `tests/test_v015_sampling.py::test_related_50_50_and_variable_halls` (1) | 4 | 4 | Active geometry and candidate-policy checks; some assertions depend on selected seed or grammar |
| `tests/test_v016_geometry_boundary.py::test_concave_sweep_recess_is_empty_and_body_occludes` (1) | 5 | 5 | Geometry or coordinate-space invariant with an explicit discriminating mathematical assertion |
| `tests/test_v016_geometry_boundary.py::test_concave_sweep_rejects_nonplanar_and_crossed_caps` (1) | 5 | 5 | Geometry or coordinate-space invariant with an explicit discriminating mathematical assertion |
| `tests/test_v016_geometry_boundary.py::test_concave_sweep_rotated_caps_are_equivalent` (1) | 5 | 5 | Geometry or coordinate-space invariant with an explicit discriminating mathematical assertion |
| `tests/test_v016_geometry_boundary.py::test_concave_sweep_side_normal_faces_into_recess` (1) | 5 | 5 | Geometry or coordinate-space invariant with an explicit discriminating mathematical assertion |
| `tests/test_v016_geometry_boundary.py::test_frozen_scene_renders_all_four` (6) | 4 | 5 | Core mesh/renderer integration, roundtrip, and frozen geometry contract |
| `tests/test_v016_geometry_boundary.py::test_mesh_scene_cli_roundtrip` (1) | 4 | 5 | Core mesh/renderer integration, roundtrip, and frozen geometry contract |
| `tests/test_v016_geometry_boundary.py::test_nearest_hit_independent_of_triangle_order` (1) | 5 | 5 | Geometry or coordinate-space invariant with an explicit discriminating mathematical assertion |
| `tests/test_v016_geometry_boundary.py::test_revolution_normals_radial_and_caps` (1) | 5 | 5 | Geometry or coordinate-space invariant with an explicit discriminating mathematical assertion |
| `tests/test_v016_geometry_boundary.py::test_sphere_is_surface_not_tubular_hoops` (1) | 4 | 5 | Core mesh/renderer integration, roundtrip, and frozen geometry contract |
| `tests/test_wall_detail_profile.py::WallArtifactRemovalTests::test_generators_removed_not_suppressed` (1) | 4 | 3 | Current facade / decoration contract; deterministic and mostly positive assertions |
| `tests/test_wall_detail_profile.py::WallArtifactRemovalTests::test_pipeline_generated_scene_and_indexed_output` (1) | 4 | 3 | Current facade / decoration contract; deterministic and mostly positive assertions |
| `tests/test_wall_detail_profile.py::WallArtifactRemovalTests::test_wall_features_removed_with_rerolls` (1) | 4 | 3 | Current facade / decoration contract; deterministic and mostly positive assertions |

## Explicit weaknesses remaining

- `SelectionTests` remain order-dependent: shared test-class directory is progressively mutated by numbered methods. **Reliability 2/5**; should be isolated in a future follow-up.
- Fixed-seed golden hashes intentionally reject harmless geometry/compiler changes: useful for refactoring, but require an explicit human approval process for intentional art changes.
- Golden coverage is 20 images, five frozen meshes and five scenes; this is not an exhaustive visual approval of all procedural variations.
- Assertions about deterministic content ranges can be brittle if grammar catalogues are intentionally edited.
- Full-suite execution previously exceeded the time limit; targeted suites are the reliable fast feedback path until runtime is reduced.

## Verification and adversarial checks

- Golden set captured with the untouched v0.16.4 production implementation, **before test pruning**.
- Deliberately lowered sun elevation: golden test rejected **707 changed pixels** in the first reference image.
- Deliberately perturbed one compiled triangle vertex by **0.002** world units: mesh golden test rejected the change.
- Weak positive assertions were rewritten and exercised on current samples (not simply deleted).
- No production code was edited for this review.

## v0.16.6 adversarial additions

Twelve new negative-control tests (`test_golden_coverage_adversarial.py`) attack the sprite inventory by deleting, duplicating or replacing rotations, or adding an unexpected candidate, in classic/diverse/related modes. All must fail the validated oracle.

The seven selection tests now receive independent fixture copies. Their individual reliability estimates have been increased from 2/5 to 4/5. These remain qualitative scores, **not** demonstrated probabilities of fault detection.

The retained 5/5 golden tests are strong *change detection*, not independent proof that every baseline is artistically correct.
