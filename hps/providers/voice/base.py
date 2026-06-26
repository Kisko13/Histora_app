class VoiceProvider:
    name = "base"
    def synthesize(self, *, db, block_id):
        raise NotImplementedError
