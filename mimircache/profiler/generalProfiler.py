# coding=utf-8
""" this module is used for all cache replacement algorithms in python
    this module can be very slow, but you can easily plug in new algorithm.

    This module haven't been fully optimized and haven't been update for some time.

    TODO: use numda and other JIT technique to improve run time

    Author: Jason Yang <peter.waynechina@gmail.com> 2016/07

"""
# -*- coding: utf-8 -*-


import math
import numpy as np
import matplotlib.pyplot as plt
from multiprocessing import Process, Pipe, Array

from mimircache.const import *
from mimircache.utils.printing import *
from mimircache.profiler.abstract.abstractProfiler import profilerAbstract


class generalProfiler(profilerAbstract):
    def __init__(self, reader, cache_class, cache_size,
                 bin_size=-1, cache_params=None,
                 num_of_threads=DEFAULT_NUM_OF_THREADS):

        if isinstance(cache_class, str):
            cache_class = cache_name_to_class(cache_class)
        super(generalProfiler, self).__init__(cache_class, cache_size, reader)
        self.cache_params = cache_params
        self.num_of_threads = num_of_threads


        self.get_hit_rate = self.get_hit_ratio
        self.get_miss_rate = self.get_miss_ratio


        if bin_size == -1:
            self.bin_size = int(self.cache_size / DEFAULT_BIN_NUM_PROFILER)
        else:
            self.bin_size = bin_size
        self.num_of_threads = num_of_threads

        self.num_of_blocks = -1
        if self.cache_size != -1:

            self.num_of_blocks = int(math.ceil(self.cache_size / self.bin_size))

            self.HRC = np.zeros((self.num_of_blocks + 1,), dtype=np.double)
            self.MRC = np.zeros((self.num_of_blocks + 1,), dtype=np.double)

        else:
            raise RuntimeError("you input -1 as cache size")
        self.cache = None
        self.cache_list = None

        self.process_list = []
        self.cache_distribution = [[] for _ in range(self.num_of_threads)]

        # shared memory for storing MRC count
        self.MRC_shared_array = Array('i', range(self.num_of_blocks))
        for i in range(len(self.MRC_shared_array)):
            self.MRC_shared_array[i] = 0

        # dispatch different cache size to different processes, does not include size = 0
        for i in range(self.num_of_blocks):
            self.cache_distribution[i % self.num_of_threads].append((i + 1) * self.bin_size)

        # build pipes for communication between main process and children process
        # the pipe mainly sends element from main process to children
        self.pipe_list = []
        for i in range(self.num_of_threads):
            self.pipe_list.append(Pipe())
            p = Process(target=self._addOneTraceElementSingleProcess,
                        args=(self.num_of_threads, i, self.cache_class, self.cache_distribution[i],
                              self.cache_params, self.pipe_list[i][1], self.MRC_shared_array))
            self.process_list.append(p)
            p.start()

        self.calculated = False

    all = ["get_hit_count", "get_hit_ratio", "get_miss_ratio", "plotMRC", "plotHRC"]


    def addOneTraceElement(self, element):
        super().addOneTraceElement(element)

        for i in range(len(self.pipe_list)):
            # print("send out: " + element)
            self.pipe_list[i][0].send(element)

        return

    # noinspection PyMethodMayBeStatic
    def _addOneTraceElementSingleProcess(self, num_of_threads, process_num,
                                         cache_class, cache_size_list,
                                         cache_args, pipe, MRC_shared_array):
        """

        :param num_of_threads:
        :param process_num:
        :param cache_class:
        :param cache_size_list: a list of different cache size dispached to this process
        :param cache_args: the extra argument (besides size) for instantiate a cache class
        :param pipe:            for receiving cache record from main process
        :param MRC_shared_array:       storing MRC count for all cache sizes
        :return:
        """
        cache_list = []
        for i in range(len(cache_size_list)):
            if cache_args:
                cache_list.append(cache_class(cache_size_list[i], **cache_args))
            else:
                cache_list.append(cache_class(cache_size_list[i]))

        elements = pipe.recv()

        # TODO this part should be changed
        while elements[-1] != 'END_1a1a11a_ENDMARKER':
            for i in range(len(cache_list)):
                for element in elements:
                    if not cache_list[i].addElement(element):
                        MRC_shared_array[i * num_of_threads + process_num] += 1
            elements = pipe.recv()


    def run(self, buffer_size=10000):
        super().run()
        self.reader.reset()
        l = []
        for i in self.reader:
            l.append(i)
            if len(l) == buffer_size:
                self.add_elements(l)
                l.clear()
                # self.addOneTraceElement(i)
        if len(l) > 0:
            self.add_elements(l)
        self.calculate()
        self.reader.reset()


    def add_elements(self, elements):
        for element in elements:
            super().addOneTraceElement(element)
        for i in range(len(self.pipe_list)):
            self.pipe_list[i][0].send(elements)

        return

    def calculate(self):
        self.calculated = True
        for i in range(len(self.pipe_list)):
            self.pipe_list[i][0].send(["END_1a1a11a_ENDMARKER"])
            self.pipe_list[i][0].close()
        for i in range(len(self.process_list)):
            self.process_list[i].join()

        self.MRC[0] = 1
        for i in range(1, len(self.MRC), 1):
            # print(self.MRC_shared_array[i])
            self.MRC[i] = self.MRC_shared_array[i - 1] / self.num_of_trace_elements
        for i in range(1, len(self.HRC), 1):
            self.HRC[i] = 1 - self.MRC[i]


    def get_hit_count(self):
        if not self.calculated:
            self.run()

        HC = np.zeros((self.num_of_blocks + 1,), dtype=np.longlong)
        for i in range(1, len(HC), 1):
            HC[i] = self.num_of_trace_elements - self.MRC_shared_array[i - 1]
        for i in range(len(HC)-1, 0, -1):
            HC[i] = HC[i] - HC[i - 1]

        return HC

    def get_hit_ratio(self):
        if not self.calculated:
            self.run()
        return self.HRC

    def get_miss_ratio(self):
        if not self.calculated:
            self.run()
        return self.MRC

    def plotMRC(self, figname="MRC.png", **kwargs):
        if not self.calculated:
            self.run()
        try:
            num_of_blocks = self.num_of_blocks + 1
            plt.plot(range(0, self.bin_size * num_of_blocks, self.bin_size), self.MRC[:num_of_blocks])
            plt.xlabel("Cache Size")
            plt.ylabel("Miss Ratio")
            plt.title('Miss Ratio Curve', fontsize=18, color='black')
            plt.savefig(figname, dpi=600)
            INFO("plot is saved at the same directory")
            plt.show()
            plt.clf()
        except Exception as e:
            plt.savefig(figname)
            WARNING("the plotting function is not wrong, is this a headless server? {}".format(e))
            traceback.print_exc()

    def plotHRC(self, figname="HRC.png", **kwargs):
        if not self.calculated:
            self.run()
        try:
            num_of_blocks = self.num_of_blocks + 1

            plt.plot(range(0, self.bin_size * num_of_blocks, self.bin_size), self.HRC[:num_of_blocks])
            plt.xlabel("Cache Size")
            plt.ylabel("Hit Ratio")
            plt.title('Hit Ratio Curve', fontsize=18, color='black')
            plt.savefig(figname, dpi=600)
            INFO("plot is saved at the same directory")
            plt.show()
            plt.clf()
        except Exception as e:
            plt.savefig(figname)
            WARNING("the plotting function is not wrong, is this a headless server? {}".format(e))


