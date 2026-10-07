from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from argon2.low_level import Type
from neosys_pharma.domain.organisation.authentification import valider_mot_de_passe


class Argon2Passwords:
    def __init__(self):
        self.hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, type=Type.ID)
        self.dummy = self.hasher.hash('Identité inexistante : vérification à coût constant')

    def hacher(self, value):
        valider_mot_de_passe(value)
        return self.hasher.hash(value)

    def verifier(self, encoded, value):
        try:
            return self.hasher.verify(encoded or self.dummy, value)
        except (VerificationError, InvalidHashError):
            return False

    def actualiser(self, encoded, value):
        return self.hasher.hash(value) if self.hasher.check_needs_rehash(encoded) else encoded


passwords = Argon2Passwords()
