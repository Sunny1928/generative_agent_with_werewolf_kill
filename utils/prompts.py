import logging
import openai
import json

class prompts:
    def __init__(self, player_id, game_info, room_setting, logger):
        self.logger : logging.Logger = logger

        self.player_id = player_id
        self.teammate = game_info['teamate']
        self.user_role = game_info['user_role']
        self.room_setting = room_setting
        self.memory = []
        self.guess_roles = []
        self.alive = [0, 1, 2, 3, 4, 5, 6] # alive players
        self.choices = [-1] # player choices in prompts
        self.day = 0
        
        self.en_dict={
            "witch":"女巫",
            "seer":"預言家",
            "werewolf":"狼人",
            "village":"村民",
            "hunter":"獵人",
        }
        
        self.stage_detail={
            "guess_role": {
                "stage_description": "猜測玩家角色階段，你要藉由你有的資訊猜測玩家角色",
            },
            "werewolf_dialogue":{
                "stage_description":"狼人發言階段，狼人和其他狼人發言",
                "save": "我在狼人階段發言"
            },
            "werewolf":{
                "stage_description":"狼人殺人階段，狼人可以殺一位玩家",
                "save": "我在狼人殺人階段投票殺"
            },
            "seer":{
                "stage_description":"猜測玩家角色階段，預言家可以查驗其他玩家的身份",
                "save": "我查驗"
            },
            "witch_save":{
                "stage_description":"女巫階段，女巫可以使用解藥救狼刀的人",
                "save": "我決定"
            },
            "witch_poison":{
                "stage_description":"女巫階段，女巫可以使用毒藥毒人",
                "save": "我決定毒"
            },
            "dialogue":{
                "stage_description":"白天發言階段，所有玩家發言",
                "save": "我發言"
            },
            "check":{
                "stage_description":"你被殺死了，請說遺言",
                "save": "我的遺言是"
            },
            "vote1":{
                "stage_description":"白天投票階段，投票最多的人將被票出遊戲",
                "save": "我票"
            },
            "vote2":{
                "stage_description":"由於上輪平票，進行第二輪白天投票階段，投票最多的人將被票出遊戲",
                "save": "我票"
            },
            "hunter":{
                "stage_description":"獵人階段，由於你被殺了，因此你可以殺一位玩家",
                "save": "我選擇殺"
            },
        }
    
        self.init_prompt = f"""你現在正在玩狼人殺，遊戲中玩家會藉由說謊，以獲得勝利。因此，資訊只有玩家發言可能會是假的，而其他的資訊皆是真的
其遊戲設定為{self.room_setting["player_num"]}人局，角色包含{self.room_setting["werewolf"]}位狼人、{self.room_setting["village"]}位平民、{"3" if self.room_setting["hunter"] else "2"}位神職（預言家和女巫{"和獵人" if self.room_setting["hunter"] else ""}）

你是{self.player_id}號玩家，你的角色是{self.en_dict[self.user_role]}，你的勝利條件為{"殺死所有神職或是所有平民或是狼的數量多於平民加神職的數量" if self.user_role == "werewolf" else "殺死所有狼人"}\n\n"""
        
        for x in self.teammate:
            self.init_prompt += f"{x}號玩家是狼，是你的隊友\n"

    
    def __print_memory__(self):

        self.logger.debug("Memory")

        if len(self.memory[0]) == 0:
            print("無資訊")
        else: 
            for day, mem in enumerate(self.memory):
                print(f'第{day+1}天')

                for idx, i in enumerate(mem):
                    print(f'{idx+1}. {i}')

        print('\n')

    
    def agent_process(self, data):

        if int(data['stage'].split('-')[0]) != self.day:
            self.day = int(data['stage'].split('-')[0])
            self.memory.append([])
        
        
        self.logger.debug("Day "+str(self.day))
        self.__print_memory__()
        
        self.process_announcement(data['stage'], data['announcement'])
        operations = self.process_information(data['stage'], data['information'])
        return operations




    def process_announcement(self, stage, announcements):
        
        if len(announcements) == 0:
            return

        # self.logger.debug("announcements:")

        for i in announcements:
            # self.logger.debug(i)
             
            # 跳過自己的資料
            if i['user'][0] == self.player_id:
                continue
            
            if i['operation'] == 'dialogue':
                text = f"{i['user'][0]}號玩家發言: {i['description']}"

            elif i['operation'] == 'died':
                self.alive.remove(i['user'][0])
                text = f"{i['user'][0]}號玩家昨晚死了"
            
            elif i['operation'] == 'role_info':
                text = f"{i['user'][0]}號玩家{i['description'].split(')')[1]}"

            else:
                text = f"{i['description']}"
            
            self.memory[self.day-1].append(text)


    
    def process_information(self, stage, informations):

        if len(informations) == 0:
            return []
        
        day, state, prompt_type = stage.split('-')
        
        operations = []
        op_data = None
        

        self.logger.debug("Guess Roles")
        self.predict_player_roles()

        # self.logger.debug("Informations:")


        if prompt_type == 'witch':
            
            if informations[0]['description'] == '女巫救人':
                self.choices = informations[0]['target']

                response = self.prompts_response(prompt_type+'_save')
                res = response.split("，")

                text = f"{self.stage_detail[prompt_type+'_save']['save']}{res[0]}{informations[0]['target'][0]}號玩家，{res[1]}"
                self.memory[self.day-1].append(text)

                

                # 不救，可以考慮使用毒藥
                if res[0] == '不救' and len(informations)>1:
                   
                    self.choices = informations[1]['target']

                    response = self.prompts_response(prompt_type+'_poison')
                    res = response.split("，")
                    who = int(res[0].split('號')[0])


                    # 使用毒藥
                    if who != -1:
                        text = f"{self.stage_detail[prompt_type+'_poison']['save']}{response}"
                        self.memory[self.day-1].append(text)
                        
                        op_data = {
                            "stage_name" : stage,
                            "operation" : informations[1]['operation'],
                            "target" : who,
                            "chat" : 'poison'
                        }
                        # operations.append(op_data)
                    

                else:
                    op_data = {
                        "stage_name" : stage,
                        "operation" : informations[0]['operation'],
                        "target" : self.choices[0],
                        "chat" : 'save'
                    }
                    # operations.append(op_data)

                    
            
            elif informations[0]['description'] == '女巫毒人':
                self.choices = informations[0]['target']

                response = self.prompts_response(prompt_type+'_poison')
                res = response.split("，")
                who = int(res[0].split('號')[0])
                

                # 使用毒藥
                if who != -1:
                    text = f"{self.stage_detail[prompt_type+'_poison']['save']}{response}"
                    self.memory[self.day-1].append(text)

                    op_data = {
                        "stage_name" : stage,
                        "operation" : informations[0]['operation'],
                        "target" : who,
                        "chat" : 'poison'
                    }

            operations.append(op_data)



        else:
            for idx, i in enumerate(informations):
                # self.logger.debug(i)
                
                self.choices = i['target']


                response = self.prompts_response(prompt_type)
                
                text = f"{self.stage_detail[prompt_type]['save']}{response}"

                if prompt_type == 'werewolf_dialogue':
                    res = response.split("，")
                    if res[0] == "選項1":
                        text = f"我在狼人階段發言\"我同意{res[1]}的發言\"。{res[2]}"
                    elif res[0] == "選項2":
                        text = f"我在狼人階段發言\"我想刀{res[1]}，我覺得他是{res[2]}\"。{res[3]}"
                    elif res[0] == "選項3":
                        text = f"我在狼人發言階段不發言。{res[1]}"

                elif prompt_type == 'dialogue':
                    res_json = json.loads(response)
                    text = f"{res_json['最終的分析']['發言']}{res_json['最終的分析']['理由']}"


                target = -1
                if '號玩家，' in response:
                    target = int(response.split('號玩家，')[0][-1])


                if text == '':
                    text = '無操作'
                

                self.memory[self.day-1].append(text)


                op_data = {
                    "stage_name" : stage,
                    "operation" : i['operation'],
                    "target" : target,
                    "chat" : text
                }
                operations.append(op_data)

        return operations 

        
            
            


    def predict_player_roles(self):
        ''' Predict and update player roles '''

        response = self.prompts_response('guess_role')
        
        self.guess_roles= []
        for i in response.splitlines():
            self.guess_roles.append(i)


    def prompts_response(self, prompt_type):
        
        prompt = self.generate_prompts(prompt_type)
        self.logger.debug("Prompt: "+str(prompt))

        response = self.__openai_send__(prompt)
        self.logger.debug("Response: "+str(response))

        return response


    
    def generate_prompts(self, prompt_type):
        ''' Generate all stages ptompts '''

        self.prompt = self.init_prompt

        # memory
        self.prompt += f"現在是第{self.day}天{self.stage_detail[prompt_type]['stage_description']}\n"
        self.prompt += f"你的資訊為:\n"
        
        if len(self.memory[0]) == 0:
            self.prompt += "無資訊\n"
        else: 
            for day, mem in enumerate(self.memory):
                self.prompt += f'第{day+1}天\n'

                for idx, i in enumerate(mem):
                    self.prompt += f'{idx+1}. {i}\n'
            

        # guess roles
        self.prompt += "\n你猜測玩家的角色：\n"

        if len(self.guess_roles) == 0:
            self.prompt += "無資訊\n"
        else:
            for idx, i in enumerate(self.guess_roles):
                self.prompt += f'{idx}. {i}\n'


        # question
        # [你必須知道的資訊] = 上述提供資訊內容
        stage_question={
            "guess_role": f'根據以上綜合資訊，請你判斷所有{self.alive}號玩家最符合的角色及你認為正確的機率百分比(直接回答"[玩家]號玩家: [角色]，[正確的機率百分比]，[原因]"，不需要其他廢話，回答完直接結束回答)',
            "werewolf_dialogue":f'''根據以上綜合資訊，你有三個選項，請選擇其中一個選項當作發言？
1. 我同意隊友的發言。請在{self.teammate}號玩家中，選擇一位隊友(若選擇此選項，請直接回答"選項1，[玩家]號玩家，[原因]"，不需要其他廢話，回答完直接結束回答)
2. 想殺某位玩家，並猜測玩家的角色。從{self.alive}中，只能選擇一位想殺的玩家，且從預言家和女巫{"和獵人" if self.room_setting["hunter"] else ""}中選一位你認為是此玩家的角色(若選擇此選項，請直接回答"選項2，[玩家]號玩家，[角色]，[原因]"，不需要其他廢話，回答完直接結束回答)
3. 無發言(若選擇此選項，請直接回答"選項3，[原因]"，不需要其他廢話，回答完直接結束回答)
                ''',
            "werewolf":f'根據以上綜合資訊，請從{self.choices}號玩家中，選擇一位要殺的玩家並簡述原因？(直接回答"[玩家]號玩家，[原因]"，不需要其他廢話，回答完直接結束回答)',
            "seer":f'根據以上綜合資訊，請問你要從{self.choices}號玩家中，查驗哪一位玩家並簡述原因？(直接回答"[玩家]號玩家，[原因]"，不需要其他廢話，回答完直接結束回答)',
            "witch_save":f'根據以上綜合資訊，{self.choices}號玩家死了，請問你要使用解藥並簡述原因？(直接回答"[救或不救]，[原因]"，不需要其他廢話，回答完直接結束回答)',
            "witch_poison":f'根據以上綜合資訊，請你從{self.choices}號玩家中使用毒藥，或選擇-1表示不使用毒藥，並簡述原因？(直接回答"[玩家]號玩家，[原因]"，不需要其他廢話，回答完直接結束回答)',
            "dialogue-test":f'根據以上綜合資訊，簡述你的推測（20字以下）?',
            "check":f'根據以上綜合資訊，簡述你的推測（20字以下）?',
            "dialogue":'''使用JSON的形式來回答，如下所述:
在這個回答格式中，我希望你能分析多次，以獲得更完整的想法，你要確保你每句話都能以上述提供資訊內容佐證，不能無中生有。並在[最終的分析]的發言，能夠清楚的表明你的立場，一定要確保發言的正確性，說話的邏輯一定不能有錯誤。
回答格式:
{   
    "分析1": {
        "想法": "你有甚麼想法?你需要以上述提供資訊內容佐證，不能無中生有",
        "理由": "想出這個想法的理由是甚麼?你需要以上述提供資訊內容佐證，不能無中生有",
        "策略": "有了這個想法，你會怎麼做?",
        "批評": "對於想法與策略有甚麼可以批評與改進的地方或是有甚麼資訊是你理解錯誤的，請詳細說明",
    },
    "分析2": {
        "反思": "對於前一個想法的批評內容，你能做甚麼改進?你需要以上述提供資訊內容佐證，並思考活著玩家可疑的地方，不能無中生有。",
        "想法": "根據反思，你有甚麼更進一步的想法?你需要以上述提供資訊內容佐證，不能無中生有",
        "理由": "想出這個想法的理由是甚麼?你需要以上述提供資訊內容佐證，不能無中生有",
        "策略": "有了這個想法，你會怎麼做?",
        "批評": "對於想法與策略有甚麼可以批評與改進的地方或是有甚麼資訊是你理解錯誤的，請詳細說明",
    }
    ...(你能夠思考N次，以獲得更完整的發言)
    "最終的分析":{
        "反思": "對於前一個想法的批評內容，你能做甚麼改進?你需要以上述提供資訊內容佐證，並思考活著玩家可疑的地方，不能無中生有。",
        "想法": "根據反思，你有甚麼更進一步的想法?你需要以上述提供資訊內容佐證，不能無中生有",
        "理由": "想出這個想法的理由是甚麼?你需要以上述提供資訊內容佐證，不能無中生有",
        "策略": "有了這個想法，你會怎麼做?",
        "發言": "(請直接呈現你說的話即可，不添加其他附加訊息)"
    }
}
請保證你的回答可以(直接被 Python 的 json.loads 解析)，且你只提供 JSON 格式的回答，不添加其他附加信息。''',
            "vote1":f'根據以上綜合資訊，請你從{self.choices}號玩家中選一位投票，或選擇-1表示棄票，並簡述原因？(直接回答"[玩家]號玩家，[原因]"，不需要其他廢話，回答完直接結束回答)',
            "vote2":f'根據以上綜合資訊，請你從{self.choices}號玩家中選一位投票，或選擇-1表示棄票，並簡述原因？(直接回答"[玩家]號玩家，[原因]"，不需要其他廢話，回答完直接結束回答)',
            "hunter":f'根據以上綜合資訊，請你從{self.choices}號玩家中選一位殺掉，或選擇-1表示棄票，並簡述原因？(直接回答"[玩家]號玩家，[原因]"，不需要其他廢話，回答完直接結束回答)',
        }
    
        self.prompt += '\nQ:'
        self.prompt += stage_question[prompt_type]
        self.prompt += '\nA:'

        # print(self.prompt)
        
        return self.prompt
    
        
    
    def __openai_send__(self , prompt):
        """openai api send prompt , can override this."""
        
        response = openai.Completion.create(
             engine="gpt-35-turbo", # this will correspond to the custom name you chose for your deployment when you deployed a model.      
             prompt=prompt, 
             max_tokens=2000, 
             temperature=0.7, 
             stop="\n\n")
        
        res = response['choices'][0]['text']

        if '<' in res:
            res = res.split('<')[0]
        
        if not (res and res.strip()):
            self.__openai_send__(prompt)
        
        return res

    
