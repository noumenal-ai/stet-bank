import Lake
open Lake DSL

package mathesis where
  leanOptions := #[⟨`autoImplicit, false⟩]

require lean4export from git
  "https://github.com/leanprover/lean4export" @ "15f6055e299ad5b89345e533cc2192f4cc00f659"

lean_lib MathesisReplay

@[default_target]
lean_lib Mathesis where
  srcDir := "../../backend-gate"
  globs := #[Glob.andSubmodules `Mathesis]

@[default_target]
lean_exe «mathesis-adjudicate» where
  srcDir := "../../backend-gate"
  root := `MathesisAdjudicate
  supportInterpreter := true
