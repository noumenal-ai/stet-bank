import Lean
import Mathesis.Primitive.Sha256
import Mathesis.Primitive.CheckProof

open Lean

namespace Mathesis.ConstHash

abbrev NormM := StateM (Std.HashMap Expr Expr)

partial def norm (e : Expr) : NormM Expr := do
  if let some x := (← get)[e]? then return x
  let e' ← match e with
    | .mdata _ b => norm b
    | .app f a => return e.updateApp! (← norm f) (← norm a)
    | .lam _ d b _ => return e.updateLambdaE! (← norm d) (← norm b)
    | .forallE _ d b _ => return e.updateForallE! (← norm d) (← norm b)
    | .letE _ t v b _ => return e.updateLet! (← norm t) (← norm v) (← norm b) false
    | .proj _ _ b => return e.updateProj! (← norm b)
    | _ => return e
  modify (·.insert e e')
  return e'

structure St where
  out : ByteArray := .empty
  nodes : Std.HashMap Expr Nat := {}

abbrev M := ReaderT (List Name) (StateT St (Except String))

@[inline] def byte (b : UInt8) : M Unit := modify fun s => { s with out := s.out.push b }

partial def nat (n : Nat) : M Unit :=
  if n < 128 then byte n.toUInt8 else do byte (n % 128 + 128).toUInt8; nat (n / 128)

def str (s : String) : M Unit := do
  let b := s.toUTF8
  nat b.size
  modify fun st => { st with out := st.out ++ b }

partial def name : Name → M Unit
  | .anonymous => byte 0
  | .str p s => do byte 1; name p; str s
  | .num p n => do byte 2; name p; nat n

partial def level : Level → M Unit
  | .zero => byte 0
  | .succ l => do byte 1; level l
  | .max a b => do byte 2; level a; level b
  | .imax a b => do byte 3; level a; level b
  | .param p => do
    match (← read).idxOf? p with
    | some i => do byte 4; nat i
    | none => do byte 5; name p
  | .mvar _ => throw "a level metavariable has no hash"

partial def expr (e : Expr) : M Nat := do
  if let some i := (← get).nodes[e]? then return i
  match e with
  | .bvar i => do byte 0; nat i
  | .sort l => do byte 1; level l
  | .const n ls => do byte 2; name n; nat ls.length; ls.forM level
  | .app f a => do let i ← expr f; let j ← expr a; byte 3; nat i; nat j
  | .lam _ d b _ => do let i ← expr d; let j ← expr b; byte 4; nat i; nat j
  | .forallE _ d b _ => do let i ← expr d; let j ← expr b; byte 5; nat i; nat j
  | .letE _ t v b _ => do let i ← expr t; let j ← expr v; let l ← expr b; byte 6; nat i; nat j; nat l
  | .lit (.natVal n) => do byte 7; nat n
  | .lit (.strVal s) => do byte 8; str s
  | .proj s i b => do let j ← expr b; byte 9; name s; nat i; nat j
  | .mdata .. => throw "mdata survived normalisation"
  | .fvar .. | .mvar .. => throw "a free variable or metavariable has no hash"
  let i := (← get).nodes.size
  modify fun st => { st with nodes := st.nodes.insert e i }
  return i

def names (ns : List Name) : M Unit := do nat ns.length; ns.forM name

def header : ConstantInfo → M Unit
  | .inductInfo v => do
    nat v.numParams; nat v.numIndices; names v.ctors; names v.all; byte (if v.isRec then 1 else 0)
  | .ctorInfo v => do name v.induct; nat v.cidx; nat v.numParams; nat v.numFields
  | _ => pure ()

def constant (ci : ConstantInfo) : M Unit := do
  str "stet.const.v1"
  nat (Mathesis.CheckProof.kindTag ci)
  nat ci.levelParams.length
  header ci
  let ty := (norm ci.type).run' {}
  let val? := (ci.value? (allowOpaque := false)).map fun v => (norm v).run' {}
  let t ← expr ty
  byte 0xfe
  nat t
  if let some v := val? then
    let j ← expr v
    byte 0xff
    nat j

def hash (ci : ConstantInfo) : Except String ByteArray := do
  let ((), st) ← (constant ci).run ci.levelParams |>.run {}
  return Sha256.hash st.out

def hashHex (ci : ConstantInfo) : Except String String := Sha256.hex <$> hash ci

end Mathesis.ConstHash
