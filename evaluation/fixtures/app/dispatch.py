class Base:
    def run(self):
        return "base"


class Child(Base):
    def run(self):
        return "child"


def dispatch(worker):
    return worker.run()
