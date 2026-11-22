import Ref

theorem honest : 0 < Budget + 1 := Nat.lt_of_lt_of_le budget_pos (Nat.le_succ _)
