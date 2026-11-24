import Lean
open Lean

def sharedValue : Nat → Expr
  | 0 => mkApp2 (mkConst ``Classical.choice [.succ .zero]) (mkConst ``Nat)
      (mkApp2 (mkConst ``Nonempty.intro [.succ .zero]) (mkConst ``Nat) (mkNatLit 0))
  | n + 1 =>
    let e := sharedValue n
    .proj ``Prod 0 (mkApp4 (mkConst ``Prod.mk [.zero, .zero]) (mkConst ``Nat) (mkConst ``Nat) e e)

run_meta addDecl <| .defnDecl <|
  mkDefinitionValEx `shared [] (mkConst ``Nat) (sharedValue 48) .opaque .safe [`shared]

theorem sharedExists : ∃ n : Nat, n = shared := ⟨shared, rfl⟩
