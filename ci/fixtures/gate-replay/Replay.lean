def parity : Nat → Nat → Prop := fun a b => a % 2 = b % 2

def Parity : Type := Quot parity

def Parity.isEven : Parity → Bool :=
  Quot.lift (fun n => n % 2 == 0) (fun _ _ h => by simp only [parity] at h; simp [h])

theorem quotLiftComputes : Parity.isEven (Quot.mk parity 4) = true := rfl

theorem quotSoundUsed : (Quot.mk parity 1 : Parity) = Quot.mk parity 3 :=
  Quot.sound rfl

theorem sorried : 1 + 1 = 3 := sorry
