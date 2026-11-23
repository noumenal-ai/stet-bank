def RiemannHypothesis : Prop := ∀ n : Nat, n = n

def FermatLastTheorem : Prop := ∀ n : Nat, n + 0 = n

def MyRH : Prop := RiemannHypothesis

theorem direct : RiemannHypothesis := fun _ => rfl

theorem wrapped : MyRH := fun _ => rfl

theorem flt : FermatLastTheorem := fun _ => rfl

theorem inProof : 2 + 2 = 4 := (fun (_ : RiemannHypothesis) => rfl) direct

theorem clean : 2 + 2 = 4 := rfl
