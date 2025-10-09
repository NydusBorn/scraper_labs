class bi_directional_iterator:
    def __init__(self, indexable):
        self.inner = indexable
        self.index = 0
        
    def next(self):
        if self.index >= len(self.inner):
            raise StopIteration
        else:
            self.index += 1
            return self.inner[self.index - 1]
    
    def prev(self):
        if self.index <= 0:
            raise StopIteration
        else:
            self.index -= 1
            return self.inner[self.index]

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

if __name__ == "__main__":
    a = bi_directional_iterator(range(1,5))
    print(a.next())
    print(a.next())
    print(a.prev())