import Lean
import Lean4Checker.Replay

namespace Mathesis

def replayKernel (env : Lean.Environment) (constMap : Std.HashMap Lean.Name Lean.ConstantInfo) :
    IO Lean.Environment :=
  env.replay' constMap

end Mathesis
