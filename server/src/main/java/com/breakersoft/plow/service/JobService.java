package com.breakersoft.plow.service;

import com.breakersoft.plow.Job;
import com.breakersoft.plow.Task;
import com.breakersoft.plow.thrift.TaskState;

public interface JobService {

    Task getTask(String id);

    boolean setTaskState(Task task, TaskState currentState, TaskState newState);

    boolean hasWaitingFrames(Job job);

    Job getJob(String id);

    boolean hasPendingFrames(Job job);

}
