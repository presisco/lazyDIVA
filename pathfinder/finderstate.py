class FinderState(object):
    def __init__(self, path_step, action_chosen=None,
                 history_state=None, action_prob=None,
                 pre_state=None, post_state=None):

        if pre_state is None and post_state is None:
            if isinstance(path_step, list):
                self.path = path_step
                self.entities = []
                for i in range(0, len(self.path), 2):
                    self.entities.append(self.path[i])
            else:
                self.path = [path_step]
                self.entities = [path_step]

            self.action_probs = []

            if action_chosen is not None:
                self.action_chosen = [action_chosen]
            else:
                self.action_chosen = []

            self.history_state = history_state
            return

        if len(path_step) == 2:
            new_ent = path_step[1]
        else:
            new_ent = path_step[0]

        if pre_state is not None:
            self.path = pre_state.path + path_step
            self.entities = pre_state.entities + [new_ent]
            self.action_probs = pre_state.action_probs + [action_prob]
            self.action_chosen = pre_state.action_chosen + [action_chosen]

        if post_state is not None:
            self.path = path_step + post_state.path
            self.entities = [new_ent] + post_state.entities
            self.action_probs = [action_prob] + post_state.action_probs
            self.action_chosen = [action_chosen] + post_state.action_chosen

        self.history_state = history_state

    def __str__(self):
        return " -> ".join(map(lambda num: str(num), self.path))

    __repr__ = __str__
