import Lean
import Mathesis.Primitive.Sha256
import Mathesis.Primitive.ConstHash

open Lean Mathesis

def nistVectors : List (String × String) := [
  ("", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
  ("abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
  ("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
    "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"),
  ("abcdefghbcdefghicdefghijdefghijkefghijklfghijklmghijklmnhijklmnoijklmnopjklmnopqklmnopqrlmnopqrsmnopqrstnopqrstu",
    "cf5b16a778af8380036ce59e7b0492370b249b11e8f07a51afac45037afee9d1"),
  ("".pushn 'a' 1000000, "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0")]

def selfTest : IO UInt32 := do
  let mut bad := 0
  for (msg, want) in nistVectors do
    let got := Sha256.hex (Sha256.hash msg.toUTF8)
    if got == want then
      IO.println s!"  PASS  sha256 of {msg.length} bytes"
    else
      IO.println s!"  FAIL  sha256 of {msg.length} bytes: {got} != {want}"
      bad := bad + 1
  return if bad == 0 then 0 else 1

def hashLine (n : Name) (ci : ConstantInfo) : Except String String :=
  (· ++ "\t" ++ n.toString) <$> ConstHash.hashHex ci

def chunked (xs : Array (Name × ConstantInfo)) (parts : Nat) : Array (Array (Name × ConstantInfo)) :=
  let size := (xs.size + parts - 1) / parts
  (List.range parts).toArray.map fun i => xs.extract (i * size) ((i + 1) * size)

def writeList (module : Name) (out : System.FilePath) (threads : Nat) : IO UInt32 := do
  initSearchPath (← findSysroot)
  let env ← importModules #[{ module }] {} (trustLevel := 1024)
  let safe := env.constants.map₁.toArray.filter (!·.2.isUnsafe)
  let tasks := (chunked safe threads).map fun part =>
    Task.spawn fun _ => part.mapM fun (n, ci) => hashLine n ci
  let mut lines : Array String := #[]
  for t in tasks do
    match t.get with
    | .ok ls => lines := lines ++ ls
    | .error e =>
      IO.eprintln s!"FATAL: {e}"
      return 1
  let sorted := lines.qsort fun a b => (a.drop 65) < (b.drop 65)
  IO.FS.withFile out .write fun h => do
    h.putStrLn s!"# stet constant hashes v1 {module} {Lean.versionString} {sorted.size}"
    for l in sorted do
      h.putStrLn l
  IO.println s!"{sorted.size} constants hashed from {module}, {env.constants.map₁.size - safe.size} unsafe skipped"
  return 0

def main (args : List String) : IO UInt32 := do
  match args with
  | ["--self-test"] => selfTest
  | ["--sha256", path] =>
    IO.println (Sha256.hex (Sha256.hash (← IO.FS.readBinFile path)))
    return 0
  | [module, out] => writeList module.toName out 8
  | [module, out, threads] => writeList module.toName out threads.toNat!
  | _ =>
    IO.eprintln "usage: mathesis-hashes --self-test | --sha256 <file> | <module> <out> [threads]"
    return 2
