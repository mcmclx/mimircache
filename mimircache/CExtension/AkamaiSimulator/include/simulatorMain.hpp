//
//  simulatorMain.hpp
//  mimircache
//
//  Created by Juncheng Yang on 7/11/17.
//  Copyright © 2017 Juncheng. All rights reserved.
//

#ifndef simulatorMain_hpp
#define simulatorMain_hpp



#ifdef __cplusplus
extern "C"
{
#endif
    
#include <stdio.h>
#include <glib.h>
#include <unistd.h>
#include <string.h> 

#ifdef __cplusplus
}
#endif


#include <iostream>
#include <algorithm> 

#include "simulator.hpp"



typedef struct {
    std::string config_loc;
    unsigned long cache_size; 
    
}simulator_arg_t;




#endif /* simulatorMain_hpp */